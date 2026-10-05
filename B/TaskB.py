from collections import deque
from array import array
import sys


INF = 4_000_000_000_000_000_000


def solve():
    input = sys.stdin.readline

    W, Q = map(int, input().split())

    warehouses = []

    for _ in range(W):
        warehouse_id, stock, fixed_cost, unit_cost = input().split()

        warehouses.append(
            (
                warehouse_id,
                int(stock),
                int(fixed_cost),
                int(unit_cost),
            )
        )

    # ---------------------------------------------------------
    # 1. Check whether the order can be fulfilled at all
    # ---------------------------------------------------------

    if sum(stock for _, stock, _, _ in warehouses) < Q:
        print(-1)
        return

    # ---------------------------------------------------------
    # 2. Find the minimum possible number of warehouses
    #
    # To minimise warehouse count, use the warehouses with the
    # largest stock capacities.
    # ---------------------------------------------------------

    stocks = sorted(
        (stock for _, stock, _, _ in warehouses),
        reverse=True,
    )

    total = 0
    min_warehouses = 0

    for stock in stocks:
        total += stock
        min_warehouses += 1

        if total >= Q:
            break

    K = min_warehouses

    # Lexicographic tie-breaking is based on warehouse_id,
    # so process warehouses in sorted ID order.
    warehouses.sort(key=lambda w: w[0])

    # ---------------------------------------------------------
    # DP definition
    #
    # suffix[i][k][q]
    #
    # = minimum cost of allocating exactly q units,
    #   using exactly k warehouses,
    #   considering warehouses i ... W - 1.
    #
    # A used warehouse must receive at least 1 unit.
    # ---------------------------------------------------------

    stride = Q + 1
    state_size = (K + 1) * stride

    def index(k, q):
        return k * stride + q

    # Base case:
    #
    # Using no warehouses, we can only fulfil quantity 0
    # with cost 0.
    next_dp = array("q", [INF]) * state_size
    next_dp[index(0, 0)] = 0

    suffix = [None] * (W + 1)
    suffix[W] = next_dp

    # ---------------------------------------------------------
    # Build suffix DP backwards.
    #
    # Normal transition:
    #
    # dp[k][q] =
    #     min(
    #         skip warehouse,
    #         fixed + x * unit + next[k-1][q-x]
    #     )
    #
    # where:
    #     1 <= x <= stock
    #
    # A naive loop over x would make this O(W*K*Q*Q).
    #
    # Rewrite:
    #
    # next[k-1][q-x] + fixed + unit*x
    #
    # let t = q-x:
    #
    # = next[k-1][t] - unit*t
    #   + fixed + unit*q
    #
    # Therefore we only need the minimum
    #
    # next[k-1][t] - unit*t
    #
    # over a sliding range of t values.
    #
    # We maintain that minimum with a monotonic deque.
    # ---------------------------------------------------------

    for i in range(W - 1, -1, -1):

        warehouse_id, stock, fixed_cost, unit_cost = warehouses[i]

        # Start with the "skip this warehouse" option.
        current_dp = array("q", next_dp)

        if stock > 0:

            for k in range(1, K + 1):

                dq = deque()

                previous_base = (k - 1) * stride
                current_base = k * stride

                for q in range(1, Q + 1):

                    # New candidate:
                    # t = q - 1
                    #
                    # This corresponds to allocating at least
                    # one unit to the current warehouse.
                    t = q - 1

                    previous_cost = next_dp[previous_base + t]

                    if previous_cost < INF:

                        candidate_value = (
                            previous_cost
                            - unit_cost * t
                        )

                        # Maintain increasing values in deque.
                        while (
                            dq
                            and dq[-1][1] > candidate_value
                        ):
                            dq.pop()

                        dq.append(
                            (t, candidate_value)
                        )

                    # x <= stock
                    #
                    # Since x = q - t:
                    #
                    # t >= q - stock
                    minimum_t = q - stock

                    while (
                        dq
                        and dq[0][0] < minimum_t
                    ):
                        dq.popleft()

                    if dq:

                        use_cost = (
                            fixed_cost
                            + unit_cost * q
                            + dq[0][1]
                        )

                        position = current_base + q

                        if use_cost < current_dp[position]:
                            current_dp[position] = use_cost

        suffix[i] = current_dp
        next_dp = current_dp

    best_cost = suffix[0][index(K, Q)]

    if best_cost >= INF:
        print(-1)
        return

    # ---------------------------------------------------------
    # 3. Reconstruct the lexicographically smallest solution
    #
    # Warehouses are sorted by warehouse_id.
    #
    # At each step:
    #   - try the smallest possible warehouse_id
    #   - then the smallest possible quantity
    #
    # Accept the first pair that can still lead to the globally
    # optimal cost.
    # ---------------------------------------------------------

    allocation = []

    start_index = 0
    remaining_warehouses = K
    remaining_quantity = Q
    remaining_cost = best_cost

    while remaining_warehouses > 0:

        found = False

        for j in range(start_index, W):

            (
                warehouse_id,
                stock,
                fixed_cost,
                unit_cost,
            ) = warehouses[j]

            max_quantity = min(
                stock,
                remaining_quantity,
            )

            # Smaller quantity gives the lexicographically
            # smaller (warehouse_id, quantity) pair when the
            # warehouse_id is the same.
            for quantity in range(1, max_quantity + 1):

                quantity_left = (
                    remaining_quantity - quantity
                )

                warehouses_left = (
                    remaining_warehouses - 1
                )

                tail_cost = suffix[j + 1][
                    index(
                        warehouses_left,
                        quantity_left,
                    )
                ]

                if tail_cost >= INF:
                    continue

                current_cost = (
                    fixed_cost
                    + unit_cost * quantity
                )

                if (
                    current_cost + tail_cost
                    == remaining_cost
                ):
                    allocation.append(
                        (warehouse_id, quantity)
                    )

                    start_index = j + 1

                    remaining_warehouses -= 1
                    remaining_quantity -= quantity
                    remaining_cost = tail_cost

                    found = True
                    break

            if found:
                break

    # ---------------------------------------------------------
    # Output
    # ---------------------------------------------------------

    print(K, best_cost)

    for warehouse_id, quantity in allocation:
        print(warehouse_id, quantity)


if __name__ == "__main__":
    solve()