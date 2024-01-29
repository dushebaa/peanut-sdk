import requests
import json
import os
import time


# Existing constants
CONTRACTS_URL = (
    # "https://raw.githubusercontent.com/peanutprotocol/peanut-contracts/xchain/contracts.json"
    "contracts.json"
)


CHAIN_DETAILS_PATH = "chainDetails.json"
CHAINS_URL = (
    "https://raw.githubusercontent.com/ethereum-lists/chains/master/_data/chains"
)
ICONS_URL = "https://raw.githubusercontent.com/ethereum-lists/chains/master/_data/icons"

# New URLs for additional icon sources
CRYPTO_ICONS_URL = "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color"  # append /{icon_name}.svg
# TRUST_WALLET_ICONS_URL = "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains"
TRUST_WALLET_ICONS_URL = "https://raw.githubusercontent.com/trustwallet/assets/8ee07e9d791bec6c3ada3cfac73ddfdc4f4a40b7/blockchains/"

# Generic default icon URL (replace with a valid URL of your default icon)
DEFAULT_ICON_URL = "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/generic.svg"


def check_rpc(rpc):
    print(f"Checking RPC {rpc}...")
    if rpc.startswith("wss://"):
        return False
    if "infura" in rpc.lower():
        return True
    try:
        response = requests.post(
            rpc,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=5,
        )
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        print("Error: ", e)
        return False


def get_contracts():
    if CONTRACTS_URL.startswith("https://"):
        response = requests.get(CONTRACTS_URL)
        if response.status_code == 200:
            return response.json()
    else:
        try:
            with open(CONTRACTS_URL, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading contracts from file: {e}")
    return None


def get_chain_ids(contracts):
    chain_ids = list(contracts.keys())
    # filter out all the chain ids that don't have a contract version of 3 or higher
    return [
        chain_id
        for chain_id in chain_ids
    ]


def get_chain_details(chain_id: int):
    chain_file = f"eip155-{chain_id}.json"
    response = requests.get(os.path.join(CHAINS_URL, chain_file))
    if response.status_code != 200:
        return None

    details = response.json()

    # check each rpc for liveliness and remove if dead
    rpcs = details.get("rpc", [])
    live_rpcs = [rpc for rpc in rpcs if check_rpc(rpc)]
    details["rpc"] = live_rpcs
    details["chainId"] = str(details["chainId"])

    # display a warning if no live rpcs found
    if len(live_rpcs) == 0:
        print(f"Warning: No live providers found for chain id {chain_id}")

    return details


def get_chain_icon(possible_chain_names, existing_chain_details):
    # Check if the icon already exists in the existing chain details
    existing_icon = existing_chain_details.get("icon")
    if existing_icon:
        print(f"Icon already exists for {possible_chain_names[0]}...")
        return existing_icon

    for name in possible_chain_names:
        print(f"Trying to get icon info for {name}...")
        # First attempt: Existing ICONS_URL
        icon_file = f"{name}.json"
        response = requests.get(os.path.join(ICONS_URL, icon_file))
        if response.status_code == 200:
            icon_info = response.json()[0]
            print(
                "Got icon info from ICONS_URL: ",
                icon_info["url"].replace("ipfs://", "https://ipfs.io/ipfs/"),
            )
            return {
                "url": icon_info["url"].replace("ipfs://", "https://ipfs.io/ipfs/"),
                "format": icon_info["format"],
            }

        # Second attempt: Crypto Icons
        icon_file = f"{name}.svg"
        response = requests.get(os.path.join(CRYPTO_ICONS_URL, icon_file))
        if response.status_code == 200:
            print("Got icon info from CRYPTO_ICONS_URL: ", response.url)
            return {"url": response.url, "format": "svg"}

        # Third attempt: TrustWallet Assets
        icon_file = f"{name}/info/logo.png"
        response = requests.get(os.path.join(TRUST_WALLET_ICONS_URL, icon_file))
        if response.status_code == 200:
            print("Got icon info from TRUST_WALLET_ICONS_URL: ", response.url)
            return {"url": response.url, "format": "png"}

    # If none of the above succeed, return a default icon
    print(
        "Failed to get icon info. Returning default icon. Failed for names: ",
        possible_chain_names,
    )
    return {"url": DEFAULT_ICON_URL, "format": "png"}


def main():
    contracts = get_contracts()
    if not contracts:
        print("Failed to get contracts.")
        return

    TESTNETS = [
        int(chain_id)
        for chain_id, details in contracts.items()
        if not details.get("mainnet")
    ]
    print(f"Found {len(TESTNETS)} testnets.")

    chain_ids = get_chain_ids(contracts)
    print(
        f"Found {len(chain_ids)} chain ids with a v3 / v4 & B4 chain id. Fetching details..."
    )

    # Load existing chain details if the file exists
    if os.path.exists(CHAIN_DETAILS_PATH):
        with open(CHAIN_DETAILS_PATH, "r") as file:
            chain_details = json.load(file)
    else:
        chain_details = {}

    for chain_id in chain_ids:
        # Only fetch details if chain_id is not already in chainDetails.json
        if chain_id in chain_details:
            user_input = input(
                f"Chain id {chain_id} already exists in chainDetails.json. Overwrite? (y/n) "
            )
            if user_input.lower() != "y":
                continue
        print(f"Fetching details for chain id {chain_id}...")

        # wait 1 second between requests to avoid rate limiting
        time.sleep(1)

        details = get_chain_details(chain_id)
        details["mainnet"] = (
            contracts[str(chain_id)].get("mainnet", "false").lower() == "true"
        )

        if not details:
            continue

        if chain_id in chain_details:
            # Add newly fetched fields that don't yet exist
            # in the current entry in chain_details
            new_details = { **details, **chain_details[chain_id] }

            # and update a few specific fields
            new_details['rpc'] = details['rpc']
            new_details['faucets'] = details['faucets']
            new_details['explorers'] = details['explorers']
            new_details['infoURL'] = details['infoURL']

            chain_details[chain_id] = new_details
            continue

        # Implicit else: create a new entry in chain_details
        # get icon
        possible_chain_names = []
        if details.get("icon"):
            possible_chain_names.append(details["icon"])
        if details.get("short_name"):
            possible_chain_names.append(details["short_name"])
        if details.get("shortName"):
            possible_chain_names.append(details["shortName"])
        if details.get("name"):
            possible_chain_names.append(details["name"])
            # also split the name by spaces and add each word to the list
            # possible_chain_names.extend(details["name"].split(" "))
        if details.get("chain"):
            possible_chain_names.append(details["chain"])
        possible_chain_names.extend([name.lower() for name in possible_chain_names])
        icon = get_chain_icon(possible_chain_names, chain_details.get(chain_id, {}))
        details["icon"] = icon

        chain_details[chain_id] = details

    with open(CHAIN_DETAILS_PATH, "w") as file:
        json.dump(chain_details, file, indent="\t")

    print("Done. Processed", len(chain_details), "chain ids: ", chain_details.keys())


# Call the function to start the process
main()
