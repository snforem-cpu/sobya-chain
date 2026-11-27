# SOBYA Validator Recruitment — Publication Pack

**Current wording: SOBYA Mainnet is live. This publication pack invites independent operators to join the existing network.**\n\n## X post (English)

SOBYA Mainnet is live (CometBFT chain ID `sobya-1`, EVM chain ID `357812033857`). We invite experienced Cosmos SDK / CometBFT operators to join the existing network as independent validators or full nodes.

We are looking for operators who control their own Linux infrastructure, can maintain reliable uptime, and can provide public P2P connectivity. Validators keep their own signing keys; SOBYA will never ask for seed phrases or private keys.

This is an invitation to join an operational network, not an investment offer. The protocol validator reserve and eligibility rules are documented in sobya/TOKENOMICS.md; participation does not promise fiat income, reimbursement, market price, liquidity, or exchange listing.

Read the operator preparation guide: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## X post (Arabic)

شبكة SOBYA الرئيسية تعمل ومنشورة بالفعل (معرّف CometBFT: `sobya-1`، ومعرّف EVM: `357812033857`). نفتح باب الانضمام للمشغلين ذوي الخبرة في Cosmos SDK وCometBFT لتشغيل مدققين وعقد مستقلة ضمن الشبكة الحالية.

نبحث عن مشغلين يمتلكون خوادم Linux مستقلة واتصالاً مستقراً وإمكانية فتح اتصال P2P. يحتفظ كل مدقق بمفاتيح التوقيع لديه، ولن نطلب أبداً العبارة السرية أو المفتاح الخاص.

هذه دعوة للانضمام إلى شبكة عاملة وليست عرضاً استثمارياً. توجد مخصصات ومواعيد لاستحقاق مكافآت المدققين وفق قواعد البروتوكول المنشورة، لكنها لا تضمن دخلاً نقدياً أو سعراً سوقياً أو سيولة أو إدراجاً في منصة.

دليل المشغلين: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## Telegram pinned message (Arabic)

**مرحباً بمهتمي تشغيل عقد SOBYA**

شبكة SOBYA الرئيسية تعمل حالياً. نستقبل طلبات المشغلين الراغبين في الانضمام إلى الشبكة القائمة بعقد مستقلة.

الأدوار المطلوبة:
- Validator: عقدة تشارك في الإجماع.
- Seed: عقدة تساعد في اكتشاف الأقران.
- RPC / Full node: عقدة غير مدققة لتقديم الاستعلامات بعد تأمينها.

يرجى إرسال معلومات عامة فقط: اسم المشغل، وسيلة التواصل، المنطقة الجغرافية العامة، مواصفات الخادم، نظام Linux، الخبرة السابقة، والدور المطلوب. لا ترسلوا كلمات مرور أو مفاتيح أو عبارات استرداد أو ملفات keyring أو ملفات validator.

الشبكة الرئيسية قائمة بالفعل. ينضم المدقق الجديد إلى السلسلة الحالية بعد مزامنة العقدة والتحقق من الإصدار ومعلمات Staking والأقران. لا تنشئوا Genesis جديداً ولا تستخدموا معرّفات CI أو عناوين أقران قديمة.

تخضع مكافآت المدققين لمخصصات البروتوكول وشرط الاستحقاق؛ ولا يوجد ضمان لقيمة سوقية أو دخل نقدي أو تعويض تكاليف. دليل الانضمام: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## Operator application template

- Operator/team:
- Contact:
- Country / broad region:
- Hosting provider:
- Linux distribution/version:
- CPU / RAM / SSD:
- Expected uptime / maintenance window:
- Inbound P2P TCP available?:
- Cosmos SDK / CometBFT experience:
- Preferred role: validator / seed / RPC / full node:

Do not include credentials, account IDs, private keys, mnemonics, seed phrases, keyring archives, or validator signing files.

## FAQ

**Is SOBYA Mainnet live?** Yes. The production network is live with CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`. New validators join the existing chain.

**Do I need to send my validator key to the project?** Never. Generate and retain it locally. Only public details and the signed gentx are shared when the official ceremony begins.

**Will I earn money or guaranteed tokens?** Validator distributions follow the protocol reserve and signing-eligibility rules in `sobya/TOKENOMICS.md`; no fiat return, market price, liquidity, exchange listing, or infrastructure reimbursement is promised.

**Can I use a GitHub Actions runner as my validator?** No. CI runners are temporary and are for tests/builds only.

**Can I use EVM ID 777777?** No. It is reserved for local development/CI. SOBYA Mainnet uses EVM chain ID `357812033857`.

## Before publishing

The project owner must add/confirm the official Telegram group, X account, and contact method. Do not invent handles, addresses, launch dates, peer endpoints, chain IDs, or RPC URLs. The recruitment guide and public repository should be accessible before inviting operators.
