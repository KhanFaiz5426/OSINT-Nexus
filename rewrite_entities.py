import sys

with open('backend/app/api/entities.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace {entity_id} with {entity_id:path} globally
lines = [l.replace('{entity_id}', '{entity_id:path}') for l in lines]

# Find the get_entity function boundaries
start = -1
end = -1
for i, l in enumerate(lines):
    if l.startswith('@router.get("/entities/{entity_id:path}", response_model=EntityResponse)'):
        start = i
    elif start != -1 and l.startswith('@router.get("/entities/{entity_id:path}/evidence"'):
        end = i - 2
        break

get_entity_lines = lines[start:end]

# Remove from original place
lines = lines[:start] + lines[end:]

# Find where to insert (before # ── Helpers)
insert_idx = -1
for i, l in enumerate(lines):
    if l.startswith('# ── Helpers'):
        insert_idx = i
        break

# Insert before helpers
lines = lines[:insert_idx] + get_entity_lines + ['\n\n'] + lines[insert_idx:]

with open('backend/app/api/entities.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
