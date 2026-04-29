import logic

def test_available_zero():
    balance = 20000
    reserve = 10000
    goal = 5000
    living_minimum = 5000
    days = 10
    amount = 500
    
    # available = 20000 - 10000 - 5000 - 5000 = 0
    
    print(f"Testing with balance={balance}, reserve={reserve}, goal={goal}, living_minimum={living_minimum}, days={days}")
    
    limit = logic.calculate_daily_limit(balance, reserve, goal, living_minimum, days)
    print(f"Daily limit: {limit}")
    
    verdict_type, response = logic.build_smart_response(balance, reserve, goal, days, amount, living_minimum)
    print(f"Verdict: {verdict_type}")
    print("Response:")
    print(response)

if __name__ == "__main__":
    test_available_zero()
