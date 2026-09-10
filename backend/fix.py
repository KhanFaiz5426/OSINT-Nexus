with open("app/api/entity_ai.py", "r") as f:
    lines = f.readlines()
lines[220] = '        \'  "connection_to_target": "<string: how this entity connects to the investigation target>",\\n\'  # noqa: E501\n'
with open("app/api/entity_ai.py", "w") as f:
    f.writelines(lines)
