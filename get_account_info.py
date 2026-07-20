"""
Calls /oauth/userinfo to get the account_id and base_uri that DocuSign
actually wants us to use for API calls -- these shouldn't be guessed or
hardcoded, since they can vary by account.
"""

from auth import get_access_token, get_user_info

if __name__ == "__main__":
    token = get_access_token()
    info = get_user_info(token)

    account = info["accounts"][0]
    print("Account ID:", account["account_id"])
    print("Base URI:", account["base_uri"])
    print("Is default account:", account["is_default"])
