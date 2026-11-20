use borsh::{BorshDeserialize, BorshSerialize};
use solana_program::{
    account_info::{next_account_info, AccountInfo},
    clock::Clock,
    entrypoint,
    entrypoint::ProgramResult,
    program::{invoke, invoke_signed},
    program_error::ProgramError,
    pubkey::Pubkey,
    rent::Rent,
    system_instruction, system_program,
    sysvar::Sysvar,
};
use spl_token::{
    instruction as token_instruction,
    state::Account as SplAccount,
};
use solana_program::program_pack::Pack;

entrypoint!(process_instruction);

const MAX_ATTESTORS: usize = 16;
const CONFIG_SEED: &[u8] = b"config";
const ORDER_SEED: &[u8] = b"order";

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug, PartialEq)]
pub struct Config {
    pub authority: Pubkey,
    pub bump: u8,
    pub usdt_mint: Pubkey,
    pub sobya_chain_id: u64,
    pub threshold: u8,
    pub attestors: Vec<Pubkey>,
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug, PartialEq)]
pub enum OrderStatus {
    Funded,
    Claimed,
    Refunded,
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug, PartialEq)]
pub struct Order {
    pub order_id: [u8; 32],
    pub user: Pubkey,
    pub solver: Pubkey,
    pub destination_recipient: [u8; 20],
    pub destination_amount: u128,
    pub source_amount: u64,
    pub quote_expiry: u64,
    pub refund_after: u64,
    pub destination_tx_hash: [u8; 32],
    pub attested_bitmap: u16,
    pub status: OrderStatus,
    pub bump: u8,
}

#[derive(BorshSerialize, BorshDeserialize, Debug)]
pub enum EscrowInstruction {
    Initialize {
        usdt_mint: Pubkey,
        sobya_chain_id: u64,
        attestors: Vec<Pubkey>,
        threshold: u8,
    },
    Fund {
        order_id: [u8; 32],
        destination_recipient: [u8; 20],
        destination_amount: u128,
        source_amount: u64,
        quote_expiry: u64,
        refund_after: u64,
    },
    AttestPayout {
        order_id: [u8; 32],
        destination_tx_hash: [u8; 32],
    },
    Claim {
        order_id: [u8; 32],
    },
    Refund {
        order_id: [u8; 32],
    },
}

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let instruction = EscrowInstruction::try_from_slice(instruction_data)
        .map_err(|_| ProgramError::InvalidInstructionData)?;
    match instruction {
        EscrowInstruction::Initialize { usdt_mint, sobya_chain_id, attestors, threshold } =>
            process_initialize(program_id, accounts, usdt_mint, sobya_chain_id, attestors, threshold),
        EscrowInstruction::Fund { order_id, destination_recipient, destination_amount, source_amount, quote_expiry, refund_after } =>
            process_fund(program_id, accounts, order_id, destination_recipient, destination_amount, source_amount, quote_expiry, refund_after),
        EscrowInstruction::AttestPayout { order_id, destination_tx_hash } =>
            process_attest(program_id, accounts, order_id, destination_tx_hash),
        EscrowInstruction::Claim { order_id } =>
            process_claim(program_id, accounts, order_id),
        EscrowInstruction::Refund { order_id } =>
            process_refund(program_id, accounts, order_id),
    }
}

fn process_initialize(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    usdt_mint: Pubkey,
    sobya_chain_id: u64,
    attestors: Vec<Pubkey>,
    threshold: u8,
) -> ProgramResult {
    let account_info_iter = &mut accounts.iter();
    let payer = next_account_info(account_info_iter)?;
    let config_account = next_account_info(account_info_iter)?;
    let system_program_account = next_account_info(account_info_iter)?;
    if !payer.is_signer || !payer.is_writable || !config_account.is_writable {
        return Err(ProgramError::MissingRequiredSignature);
    }
    if system_program_account.key != &system_program::id() {
        return Err(ProgramError::IncorrectProgramId);
    }
    if usdt_mint == Pubkey::default() || sobya_chain_id == 0 || attestors.is_empty()
        || attestors.len() > MAX_ATTESTORS || threshold == 0 || threshold as usize > attestors.len()
    {
        return Err(ProgramError::InvalidArgument);
    }
    for i in 0..attestors.len() {
        if attestors[i] == Pubkey::default()
            || attestors[..i].iter().any(|prior| prior == &attestors[i])
        {
            return Err(ProgramError::InvalidArgument);
        }
    }

    let (expected_config, bump) = Pubkey::find_program_address(&[CONFIG_SEED, payer.key.as_ref()], program_id);
    if config_account.key != &expected_config || config_account.owner != &system_program::id()
        || !config_account.data_is_empty()
    {
        return Err(ProgramError::InvalidAccountData);
    }

    let config = Config { authority: *payer.key, bump, usdt_mint, sobya_chain_id, threshold, attestors };
    let data = borsh::to_vec(&config).map_err(|_| ProgramError::InvalidAccountData)?;
    let rent = Rent::get()?;
    let lamports = rent.minimum_balance(data.len());
    let bump_seed = [bump];
    let signer_seeds: &[&[u8]] = &[CONFIG_SEED, payer.key.as_ref(), &bump_seed];
    invoke_signed(
        &system_instruction::create_account(payer.key, config_account.key, lamports, data.len() as u64, program_id),
        &[payer.clone(), config_account.clone(), system_program_account.clone()],
        &[signer_seeds],
    )?;
    config_account.data.borrow_mut().copy_from_slice(&data);
    Ok(())
}

fn process_fund(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    order_id: [u8; 32],
    destination_recipient: [u8; 20],
    destination_amount: u128,
    source_amount: u64,
    quote_expiry: u64,
    refund_after: u64,
) -> ProgramResult {
    let account_info_iter = &mut accounts.iter();
    let user = next_account_info(account_info_iter)?;
    let solver = next_account_info(account_info_iter)?;
    let config_account = next_account_info(account_info_iter)?;
    let order_account = next_account_info(account_info_iter)?;
    let user_token = next_account_info(account_info_iter)?;
    let escrow_token = next_account_info(account_info_iter)?;
    let token_program = next_account_info(account_info_iter)?;
    let system_program_account = next_account_info(account_info_iter)?;

    if !user.is_signer || !user.is_writable || !solver.is_signer || !order_account.is_writable {
        return Err(ProgramError::MissingRequiredSignature);
    }
    if token_program.key != &spl_token::id() || system_program_account.key != &system_program::id() {
        return Err(ProgramError::IncorrectProgramId);
    }
    let config = load_config(program_id, config_account)?;
    let now = Clock::get()?.unix_timestamp.max(0) as u64;
    if order_id == [0; 32] || destination_recipient == [0; 20] || destination_amount == 0
        || source_amount == 0 || quote_expiry <= now || refund_after <= quote_expiry
    {
        return Err(ProgramError::InvalidArgument);
    }

    let (expected_order, bump) = Pubkey::find_program_address(&[ORDER_SEED, &order_id], program_id);
    if order_account.key != &expected_order || order_account.owner != &system_program::id()
        || !order_account.data_is_empty()
    {
        return Err(ProgramError::InvalidAccountData);
    }

    let user_token_state = SplAccount::unpack(&user_token.data.borrow())?;
    let escrow_token_state = SplAccount::unpack(&escrow_token.data.borrow())?;
    if user_token_state.owner != *user.key || user_token_state.mint != config.usdt_mint
        || escrow_token_state.owner != expected_order || escrow_token_state.mint != config.usdt_mint
    {
        return Err(ProgramError::InvalidAccountData);
    }

    let order = Order {
        order_id, user: *user.key, solver: *solver.key, destination_recipient,
        destination_amount, source_amount, quote_expiry, refund_after,
        destination_tx_hash: [0; 32], attested_bitmap: 0,
        status: OrderStatus::Funded, bump,
    };
    let data = borsh::to_vec(&order).map_err(|_| ProgramError::InvalidAccountData)?;
    let rent = Rent::get()?;
    invoke_signed(
        &system_instruction::create_account(user.key, order_account.key, rent.minimum_balance(data.len()), data.len() as u64, program_id),
        &[user.clone(), order_account.clone(), system_program_account.clone()],
        &[&[ORDER_SEED, &order_id, &[bump]]],
    )?;

    let before = SplAccount::unpack(&escrow_token.data.borrow())?.amount;
    let transfer_ix = token_instruction::transfer(token_program.key, user_token.key, escrow_token.key, user.key, &[], source_amount)?;
    invoke(&transfer_ix, &[user_token.clone(), escrow_token.clone(), user.clone(), token_program.clone()])?;
    let after = SplAccount::unpack(&escrow_token.data.borrow())?.amount;
    if after.checked_sub(before) != Some(source_amount) {
        return Err(ProgramError::InvalidAccountData);
    }
    order.serialize(&mut &mut order_account.data.borrow_mut()[..])
        .map_err(|_| ProgramError::AccountDataTooSmall)?;
    Ok(())
}

fn process_attest(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    order_id: [u8; 32],
    destination_tx_hash: [u8; 32],
) -> ProgramResult {
    let account_info_iter = &mut accounts.iter();
    let attestor = next_account_info(account_info_iter)?;
    let config_account = next_account_info(account_info_iter)?;
    let order_account = next_account_info(account_info_iter)?;
    if !attestor.is_signer || !order_account.is_writable || destination_tx_hash == [0; 32] {
        return Err(ProgramError::MissingRequiredSignature);
    }
    let config = load_config(program_id, config_account)?;
    let (expected_order, _) = Pubkey::find_program_address(&[ORDER_SEED, &order_id], program_id);
    if order_account.key != &expected_order || order_account.owner != program_id {
        return Err(ProgramError::InvalidAccountData);
    }
    let mut order = load_order(order_account)?;
    if order.order_id != order_id || order.status != OrderStatus::Funded {
        return Err(ProgramError::InvalidAccountData);
    }
    let index = config.attestors.iter().position(|key| key == attestor.key)
        .ok_or(ProgramError::IllegalOwner)?;
    let bit = 1u16.checked_shl(index as u32).ok_or(ProgramError::InvalidArgument)?;
    if order.attested_bitmap & bit != 0 {
        return Err(ProgramError::InvalidArgument);
    }
    if order.destination_tx_hash == [0; 32] {
        order.destination_tx_hash = destination_tx_hash;
    } else if order.destination_tx_hash != destination_tx_hash {
        return Err(ProgramError::InvalidArgument);
    }
    order.attested_bitmap |= bit;
    save_order(order_account, &order)
}

fn process_claim(program_id: &Pubkey, accounts: &[AccountInfo], order_id: [u8; 32]) -> ProgramResult {
    let account_info_iter = &mut accounts.iter();
    let solver = next_account_info(account_info_iter)?;
    let config_account = next_account_info(account_info_iter)?;
    let order_account = next_account_info(account_info_iter)?;
    let escrow_token = next_account_info(account_info_iter)?;
    let solver_token = next_account_info(account_info_iter)?;
    let token_program = next_account_info(account_info_iter)?;
    if !solver.is_signer || !order_account.is_writable || !escrow_token.is_writable || !solver_token.is_writable {
        return Err(ProgramError::MissingRequiredSignature);
    }
    if token_program.key != &spl_token::id() {
        return Err(ProgramError::IncorrectProgramId);
    }
    let config = load_config(program_id, config_account)?;
    let (expected_order, _) = Pubkey::find_program_address(&[ORDER_SEED, &order_id], program_id);
    if order_account.key != &expected_order || order_account.owner != program_id {
        return Err(ProgramError::InvalidAccountData);
    }
    let mut order = load_order(order_account)?;
    if order.order_id != order_id || order.status != OrderStatus::Funded
        || order.solver != *solver.key || order.destination_tx_hash == [0; 32]
        || order.attested_bitmap.count_ones() < config.threshold as u32
    {
        return Err(ProgramError::InvalidAccountData);
    }
    transfer_from_order(program_id, &order, order_account, escrow_token, solver_token, solver, token_program, &config)?;
    order.status = OrderStatus::Claimed;
    save_order(order_account, &order)
}

fn process_refund(program_id: &Pubkey, accounts: &[AccountInfo], order_id: [u8; 32]) -> ProgramResult {
    let account_info_iter = &mut accounts.iter();
    let user = next_account_info(account_info_iter)?;
    let config_account = next_account_info(account_info_iter)?;
    let order_account = next_account_info(account_info_iter)?;
    let escrow_token = next_account_info(account_info_iter)?;
    let user_token = next_account_info(account_info_iter)?;
    let token_program = next_account_info(account_info_iter)?;
    if !user.is_signer || !order_account.is_writable || !escrow_token.is_writable || !user_token.is_writable {
        return Err(ProgramError::MissingRequiredSignature);
    }
    if token_program.key != &spl_token::id() {
        return Err(ProgramError::IncorrectProgramId);
    }
    let config = load_config(program_id, config_account)?;
    let (expected_order, _) = Pubkey::find_program_address(&[ORDER_SEED, &order_id], program_id);
    if order_account.key != &expected_order || order_account.owner != program_id {
        return Err(ProgramError::InvalidAccountData);
    }
    let mut order = load_order(order_account)?;
    let now = Clock::get()?.unix_timestamp.max(0) as u64;
    if order.order_id != order_id || order.status != OrderStatus::Funded
        || order.user != *user.key || now < order.refund_after
    {
        return Err(ProgramError::InvalidAccountData);
    }
    transfer_from_order(program_id, &order, order_account, escrow_token, user_token, user, token_program, &config)?;
    order.status = OrderStatus::Refunded;
    save_order(order_account, &order)
}

fn transfer_from_order(
    program_id: &Pubkey,
    order: &Order,
    order_account: &AccountInfo,
    escrow_token: &AccountInfo,
    destination_token: &AccountInfo,
    destination_owner: &AccountInfo,
    token_program: &AccountInfo,
    config: &Config,
) -> ProgramResult {
    let (expected_order, bump) = Pubkey::find_program_address(&[ORDER_SEED, &order.order_id], program_id);
    let escrow_state = SplAccount::unpack(&escrow_token.data.borrow())?;
    let destination_state = SplAccount::unpack(&destination_token.data.borrow())?;
    if escrow_state.owner != expected_order || escrow_state.mint != config.usdt_mint
        || destination_state.owner != *destination_owner.key || destination_state.mint != config.usdt_mint
    {
        return Err(ProgramError::InvalidAccountData);
    }
    let ix = token_instruction::transfer(token_program.key, escrow_token.key, destination_token.key, order_account.key, &[], order.source_amount)?;
    invoke_signed(
        &ix,
        &[escrow_token.clone(), destination_token.clone(), order_account.clone(), token_program.clone()],
        &[&[ORDER_SEED, &order.order_id, &[bump]]],
    )
}

fn load_config(program_id: &Pubkey, account: &AccountInfo) -> Result<Config, ProgramError> {
    if account.owner != program_id {
        return Err(ProgramError::InvalidAccountData);
    }
    let config = Config::try_from_slice(&account.data.borrow()).map_err(|_| ProgramError::InvalidAccountData)?;
    let (expected, _) = Pubkey::find_program_address(&[CONFIG_SEED, config.authority.as_ref()], program_id);
    if account.key != &expected {
        return Err(ProgramError::InvalidAccountData);
    }
    Ok(config)
}

fn load_order(account: &AccountInfo) -> Result<Order, ProgramError> {
    Order::try_from_slice(&account.data.borrow()).map_err(|_| ProgramError::InvalidAccountData)
}

fn save_order(account: &AccountInfo, order: &Order) -> ProgramResult {
    order.serialize(&mut &mut account.data.borrow_mut()[..])
        .map_err(|_| ProgramError::AccountDataTooSmall)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn attestor_bitmap_counts_distinct_signers() {
        let mut bitmap = 0u16;
        bitmap |= 1 << 0;
        bitmap |= 1 << 3;
        assert_eq!(bitmap.count_ones(), 2);
        assert_ne!(bitmap & (1 << 3), 0);
    }

    #[test]
    fn terminal_statuses_are_distinct() {
        assert_ne!(OrderStatus::Claimed, OrderStatus::Refunded);
        assert_ne!(OrderStatus::Funded, OrderStatus::Claimed);
    }

    #[test]
    fn order_serialization_round_trips() {
        let order = Order {
            order_id: [7; 32], user: Pubkey::new_unique(), solver: Pubkey::new_unique(),
            destination_recipient: [9; 20], destination_amount: 1_000_000_000_000_000_000,
            source_amount: 42_000_000, quote_expiry: 100, refund_after: 200,
            destination_tx_hash: [0; 32], attested_bitmap: 0,
            status: OrderStatus::Funded, bump: 254,
        };
        let bytes = borsh::to_vec(&order).unwrap();
        let decoded = Order::try_from_slice(&bytes).unwrap();
        assert_eq!(decoded, order);
    }
}
