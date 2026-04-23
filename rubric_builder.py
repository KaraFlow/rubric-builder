#!/usr/bin/env python3

import json
import os
import re
from datetime import datetime


def sanitize_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "rubric_output"


def prompt_non_empty(prompt_text: str) -> str:
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print("Input cannot be empty.")


def prompt_int(prompt_text: str, minimum: int = 0) -> int:
    while True:
        raw = input(prompt_text).strip()
        try:
            value = int(raw)
            if value < minimum:
                print(f"Enter a number greater than or equal to {minimum}.")
                continue
            return value
        except ValueError:
            print("Enter a valid integer.")


def prompt_list_counted(label: str) -> list[str]:
    items = []
    count = prompt_int(f"How many {label}? ", minimum=0)
    for i in range(count):
        item = prompt_non_empty(f"{label[:-1].capitalize()} {i + 1}: ")
        items.append(item)
    return items


def prompt_variables() -> tuple[list[str], dict[str, str]]:
    while True:
        raw = prompt_non_empty(
            "Define the evaluation variables, separated by commas: "
        )
        variables = [v.strip() for v in raw.split(",") if v.strip()]
        unique_variables = []
        seen = set()

        for var in variables:
            key = var.lower()
            if key not in seen:
                seen.add(key)
                unique_variables.append(var)

        if unique_variables:
            break

        print("Please enter at least one variable.")

    variable_details = {}
    print("\nProvide a short description for each variable.")
    for var in unique_variables:
        detail = prompt_non_empty(f'Description for "{var}": ')
        variable_details[var] = detail

    return unique_variables, variable_details


def assign_requirements_to_variables(
    requirements: list[str], variables: list[str]
) -> dict[str, list[str]]:
    mapping = {var: [] for var in variables}

    if not requirements:
        return mapping

    print("\nAssign each functional requirement to one variable.")
    for idx, requirement in enumerate(requirements, start=1):
        print(f"\nRequirement {idx}: {requirement}")
        for i, var in enumerate(variables, start=1):
            print(f"[{i}] {var}")

        while True:
            choice = input("Choose the variable number: ").strip()
            try:
                choice_int = int(choice)
                if 1 <= choice_int <= len(variables):
                    selected_var = variables[choice_int - 1]
                    mapping[selected_var].append(requirement)
                    break
                print("Choice out of range.")
            except ValueError:
                print("Enter a valid number.")

    return mapping


def build_rubric(
    task_name: str,
    task_description: str,
    variables: list[str],
    variable_details: dict[str, str],
    requirements_by_variable: dict[str, list[str]],
    strict_requirements: list[str],
    preferences: list[str],
) -> dict:
    scored_variables = [v for v in variables if requirements_by_variable.get(v)]
    weight_per_variable = round(1 / len(scored_variables), 4) if scored_variables else 0

    rubric_items = []
    for var in variables:
        linked_requirements = requirements_by_variable.get(var, [])
        criterion_type = "scored" if linked_requirements else "informational"

        verification_steps = []
        if linked_requirements:
            verification_steps.append(
                f"Check whether the output satisfies the linked requirements for '{var}'."
            )
            verification_steps.extend(
                [f"Verify: {req}" for req in linked_requirements]
            )
        else:
            verification_steps.append(
                f"Review whether the output aligns with the definition of '{var}'."
            )

        rubric_items.append(
            {
                "criterion": var,
                "description": variable_details[var],
                "type": criterion_type,
                "weight": weight_per_variable if criterion_type == "scored" else 0,
                "derived_from": linked_requirements,
                "verification": verification_steps,
                "failure_condition": (
                    f"Fails when output does not satisfy the requirements linked to '{var}'."
                    if linked_requirements
                    else f"Fails when output clearly conflicts with the definition of '{var}'."
                ),
            }
        )

    strict_checks = []
    for item in strict_requirements:
        strict_checks.append(
            {
                "requirement": item,
                "type": "strict_pass_fail",
                "verification": f"Fail immediately if this condition is violated: {item}",
            }
        )

    return {
        "metadata": {
            "task_name": task_name,
            "task_description": task_description,
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        "rubric": rubric_items,
        "strict_requirements": strict_checks,
        "preferences": preferences,
    }


def build_checklist_markdown(rubric_data: dict) -> str:
    meta = rubric_data["metadata"]
    rubric = rubric_data["rubric"]
    strict_requirements = rubric_data["strict_requirements"]
    preferences = rubric_data["preferences"]

    lines = []
    lines.append(f"# Evaluation Checklist: {meta['task_name']}")
    lines.append("")
    lines.append("## Task Description")
    lines.append(meta["task_description"])
    lines.append("")

    lines.append("## Strict Requirements")
    if strict_requirements:
        for item in strict_requirements:
            lines.append(f"- [ ] {item['requirement']}")
    else:
        lines.append("- None defined.")
    lines.append("")

    lines.append("## Scored Criteria")
    for item in rubric:
        lines.append(f"### {item['criterion']}")
        lines.append(f"- Description: {item['description']}")
        lines.append(f"- Type: {item['type']}")
        lines.append(f"- Weight: {item['weight']}")
        if item["derived_from"]:
            lines.append("- Derived from:")
            for req in item["derived_from"]:
                lines.append(f"  - {req}")
        else:
            lines.append("- Derived from: No direct functional requirement mapped.")
        lines.append("- Verification:")
        for step in item["verification"]:
            lines.append(f"  - {step}")
        lines.append(f"- Failure condition: {item['failure_condition']}")
        lines.append("")

    lines.append("## Optional Preferences")
    if preferences:
        for pref in preferences:
            lines.append(f"- [ ] {pref}")
    else:
        lines.append("- None defined.")
    lines.append("")

    return "\n".join(lines)


def save_outputs(task_name: str, rubric_data: dict, checklist_md: str) -> str:
    folder_name = sanitize_filename(task_name)
    output_dir = os.path.join(os.getcwd(), folder_name)
    os.makedirs(output_dir, exist_ok=True)

    rubric_path = os.path.join(output_dir, "rubric.json")
    checklist_path = os.path.join(output_dir, "checklist.md")

    with open(rubric_path, "w", encoding="utf-8") as f:
        json.dump(rubric_data, f, indent=2, ensure_ascii=False)

    with open(checklist_path, "w", encoding="utf-8") as f:
        f.write(checklist_md)

    return output_dir


def main() -> None:
    print("=== Rubric Builder ===\n")

    task_name = prompt_non_empty("Task name: ")
    task_description = prompt_non_empty("Task description: ")
    print()

    variables, variable_details = prompt_variables()
    print()

    functional_requirements = prompt_list_counted("functional requirements")
    print()

    strict_requirements = prompt_list_counted("strict requirements")
    print()

    preferences = prompt_list_counted("optional preferences")
    print()

    requirements_by_variable = assign_requirements_to_variables(
        functional_requirements, variables
    )

    rubric_data = build_rubric(
        task_name=task_name,
        task_description=task_description,
        variables=variables,
        variable_details=variable_details,
        requirements_by_variable=requirements_by_variable,
        strict_requirements=strict_requirements,
        preferences=preferences,
    )

    checklist_md = build_checklist_markdown(rubric_data)
    output_dir = save_outputs(task_name, rubric_data, checklist_md)

    print("\nDone.")
    print(f"Output directory: {output_dir}")
    print(f"- rubric.json")
    print(f"- checklist.md")


if __name__ == "__main__":
    main()