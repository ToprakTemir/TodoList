
while True:
    remaining_days = float(input())
    estimated_hours = float(input())
    hours_work_per_day = 12

    max_panic = 10
    safety_interval_days = 10

    panic_factor = remaining_days / (estimated_hours / hours_work_per_day) # remaining
    panic_factor -= 1
    panic_factor /= (safety_interval_days-1)
    panic_factor **= 1.5
    panic_factor = 1 - panic_factor
    panic_factor *= max_panic

    print(panic_factor)

# seperate the panic calculation into multiple lines
panic = remaining_days / (estimated_hours / hours_work_per_day)
panic -= 1
panic /= safety_interval_days - 1