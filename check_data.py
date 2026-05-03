import json

# Read the file
with open('hospital-complete-data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Show first doctor record EXACTLY as it is
doctors = data.get("doctors", [])

print("TOTAL DOCTORS:", len(doctors))
print("\n" + "="*60)
print("FIRST DOCTOR RECORD - EXACT FIELDS:")
print("="*60)

if doctors:
    first = doctors[0]
    for key, value in first.items():
        print(f"  Field: '{key}' = '{value}'")

print("\n" + "="*60)
print("SECOND DOCTOR RECORD:")
print("="*60)

if len(doctors) > 1:
    second = doctors[1]
    for key, value in second.items():
        print(f"  Field: '{key}' = '{value}'")

# Show departments
print("\n" + "="*60)
print("FIRST DEPARTMENT RECORD:")
print("="*60)

departments = data.get("departments", [])
if departments:
    first_dept = departments[0]
    for key, value in first_dept.items():
        print(f"  Field: '{key}' = '{value}'")

# Show services
print("\n" + "="*60)
print("FIRST SERVICE RECORD:")
print("="*60)

services = data.get("services", [])
if services:
    first_svc = services[0]
    for key, value in first_svc.items():
        print(f"  Field: '{key}' = '{value}'")