import argparse
import json


def classify_ticket(user_input):
    text = user_input.lower()

    if any(word in text for word in ["charged", "charge", "payment", "billing", "subscription"]):
        return "billing"

    if any(word in text for word in ["crash", "error", "upload", "bug", "broken", "technical"]):
        return "technical"

    if any(word in text for word in ["login", "log into", "password", "account"]):
        return "account"

    if any(word in text for word in ["package", "delivery", "arrived", "shipping", "shipment"]):
        return "shipping"

    return "other"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--call-index", type=int, default=0)

    args = parser.parse_args()

    category = classify_ticket(args.input)

    response = {
        "output": category,
        "finish": "stop"
    }

    print(json.dumps(response))


if __name__ == "__main__":
    main()