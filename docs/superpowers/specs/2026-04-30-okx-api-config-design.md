# OKX API Config And Demo Design

## Goal

Add OKX Web3 API credentials to KittyChain configuration, improve the API settings TUI so all API credentials can be edited in one form, and add runnable OKX API demos under `demo/`.

## Assumptions

- OKX Web3 API authenticated requests require `OK-ACCESS-KEY`, `OK-ACCESS-SIGN`, `OK-ACCESS-TIMESTAMP`, and `OK-ACCESS-PASSPHRASE`.
- The OKX credentials stored by `kittychain --config` are API Key, Secret Key, and Passphrase.
- The user's "2 files" note was a typo because the requested file list contains three files: `token_api.py`, `address_api.py`, and `transaction_api.py`.
- Demo scripts should be runnable without command-line arguments by using fixed example values and the stored OKX credentials.

## Scope

### Configuration

- Extend `ApiConfig` with:
  - `okx_api_key`
  - `okx_secret_key`
  - `okx_passphrase`
- Preserve compatibility with old config files by defaulting missing OKX fields to empty strings.
- Persist OKX fields under the existing top-level `apis` object.

### API Settings TUI

- Keep API configuration as a single form launched from the existing APIs section.
- Display all API credential inputs in one screen:
  - Dune API Key
  - GoPlus API Key
  - GoPlus API Secret
  - Alchemy API Key
  - Chainbase API Key
  - CoinGecko API Key
  - OKX API Key
  - OKX Secret Key
  - OKX Passphrase
- Let users move between inputs with normal prompt-toolkit focus navigation, including up/down keys.
- Save all API field edits together through the form's Save button, then persist through the existing main screen save flow.

### Demo Structure

- Add `demo/okx_client.py` for shared credential loading, signing, and HTTP request code.
- Add `demo/token_api.py` with one function per requested token API endpoint.
- Add `demo/address_api.py` with one function per requested address/portfolio API endpoint.
- Add `demo/transaction_api.py` with one function per requested transaction API endpoint.
- Each demo module should run all its wrapped APIs in its `__main__` branch without requiring args.
- Demo functions should accept parameters explicitly so callers can reuse them outside the hardcoded examples.

## Error Handling

- If OKX credentials are missing, demo scripts should raise a clear `ValueError` naming the missing config fields.
- Demo network failures should surface the underlying request error or OKX HTTP response body; the demos do not need retries or advanced recovery.
- The TUI should not validate whether credentials are live because that would add network behavior to configuration editing.

## Testing

- Update config tests to prove OKX fields round-trip and old configs still load.
- Update TUI tests to prove the API form includes the OKX fields and maps them back into `ApiConfig`.
- Add demo tests around OKX credential loading/signing/request construction without calling live OKX endpoints.

