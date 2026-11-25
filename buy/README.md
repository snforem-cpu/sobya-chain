# SOBYA BUY

SOBYA BUY is the original manual purchase-request desk for native SOBY.

## Manual request process

1. Enter the amount of SOBY requested.
2. Review the current reference price shown by the page.
3. Enter the payment network and currency/asset supported by the buyer's wallet.
4. Enter the amount sent, transaction ID or hash, and the EVM address that should receive SOBY.
5. Submit the request and save the returned order ID.

The form accepts manually entered payment network and asset details. It is not restricted to Ethereum or USDT.

## Important

- Submitting a request does not automatically verify payment or transfer SOBY.
- The project team reviews each payment manually and fulfils approved requests.
- Buyers must independently confirm the receiving address, network, and asset with the project before sending funds.
- Never share a seed phrase or private key.
- The reference price is informational and may be changed by the owner through the protected owner desk.

The public purchase page is served at `/buy/`. The manual order API stores submitted requests for owner review.
