import json

from agent import ask


with open("eval_questions.json", "r", encoding="utf-8") as f:
    cases = json.load(f)


print("NAVARA Evaluation")
print("=================\n")

passed = 0

for i, case in enumerate(cases, start=1):
    result = ask(case["question"])

    tools = result["tools_used"]

    if case["expected_tool"] == "none":
        actual = "none" if not tools else tools[0]
    else:
        actual = tools[0] if tools else "none"

    success = actual == case["expected_tool"]

    if success:
        passed += 1

    print(f"{i}. {case['question']}")
    print(f"   Expected: {case['expected_tool']}")
    print(f"   Actual:   {actual}")
    print(f"   Result:   {'PASS' if success else 'CHECK'}")
    print()


print(f"Tool-selection checks: {passed}/{len(cases)}")