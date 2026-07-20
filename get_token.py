"""
Milestone 1: prove JWT Grant auth works end to end against the DocuSign demo account.
"""

from auth import get_access_token

if __name__ == "__main__":
    token = get_access_token()
    print("Auth succeeded.")
    print("Access token (truncated):", token[:20] + "...")
