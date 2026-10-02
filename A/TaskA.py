import sys


def parse_command(parts):
    command = parts[0]

    try:
        if command in ("RESERVE", "RELEASE", "SHIP"):
            if len(parts) != 4:
                return None

            _, event_id, order_id, qty_str = parts
            qty = int(qty_str)

            if qty <= 0 or not event_id or not order_id:
                return None

            return command, event_id, order_id, qty

        if command == "RESTOCK":
            if len(parts) != 3:
                return None

            _, event_id, qty_str = parts
            qty = int(qty_str)

            if qty <= 0 or not event_id:
                return None

            return command, event_id, None, qty

        return None
    except ValueError:
        return None


def process_commands():
    first_line = sys.stdin.readline().strip().split()

    if len(first_line) != 2:
        return

    try:
        on_hand = int(first_line[0])
        n = int(first_line[1])
    except ValueError:
        return

    # order_id -> currently reserved quantity
    reservations = {}

    # event_ids that have already been processed
    processed_events = set()

    total_reserved = 0

    for _ in range(n):
        line = sys.stdin.readline().strip()
        parts = line.split()

        if not parts:
            continue

        parsed = parse_command(parts)
        if parsed is None:
            print(f"REJECTED {on_hand} {total_reserved}")
            continue

        command, event_id, order_id, qty = parsed

        # Idempotency check
        if event_id in processed_events:
            print(f"DUPLICATE {on_hand} {total_reserved}")
            continue

        # Once a valid command has been parsed, this event is considered processed,
        # even if the business operation itself is rejected.
        processed_events.add(event_id)

        if command == "RESERVE":
            available = on_hand - total_reserved

            if qty > available:
                print(f"REJECTED {on_hand} {total_reserved}")
                continue

            reservations[order_id] = reservations.get(order_id, 0) + qty
            #if there is a reservation for this order_id, we add the qty to it, otherwise we create a new reservation with the qty
            total_reserved += qty

            print(f"OK {on_hand} {total_reserved}")

        elif command == "RELEASE":
            current_reserved = reservations.get(order_id, 0)

            if qty > current_reserved:
                print(f"REJECTED {on_hand} {total_reserved}")
                continue

            reservations[order_id] = current_reserved - qty
            total_reserved -= qty

            if reservations[order_id] == 0:
                del reservations[order_id]

            print(f"OK {on_hand} {total_reserved}")

        elif command == "SHIP":
            current_reserved = reservations.get(order_id, 0)

            if qty > current_reserved:
                print(f"REJECTED {on_hand} {total_reserved}")
                continue

            reservations[order_id] = current_reserved - qty
            total_reserved -= qty
            on_hand -= qty

            if reservations[order_id] == 0:
                del reservations[order_id]

            print(f"OK {on_hand} {total_reserved}")

        elif command == "RESTOCK":
            on_hand += qty

            print(f"OK {on_hand} {total_reserved}")

    # Final output: open reservations ordered by order_id
    open_orders = sorted(reservations.items())

    print(f"OPEN {len(open_orders)}")

    for order_id, qty in open_orders:
        print(f"{order_id} {qty}")


if __name__ == "__main__":
    process_commands()