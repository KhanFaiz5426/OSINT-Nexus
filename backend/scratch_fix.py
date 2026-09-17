import re
import os

def fix_file(filepath, replacements, need_uuid=True):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if need_uuid and 'import uuid' not in content:
        content = content.replace('import json', 'import json\nimport uuid')
        
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
        else:
            print(f'Failed to find {old!r} in {filepath}')
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('app/services/orchestrator.py', [
    ('''
                INSERT INTO observations
                    (investigation_id, source_adapter, source_version, collected_at,
                     method, target, raw_response, normalized_value, confidence, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id::text
                """,
                investigation_id,''', 
    '''
                INSERT INTO observations
                    (id, investigation_id, source_adapter, source_version, collected_at,
                     method, target, raw_response, normalized_value, confidence, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id::text
                """,
                str(uuid.uuid4()),
                investigation_id,''')
])

fix_file('app/services/correlator.py', [
    ('''
                        INSERT INTO entity_provenance (entity_id, observation_id, investigation_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (entity_id, observation_id) DO NOTHING
                        """,
                        entity.id,''',
    '''
                        INSERT INTO entity_provenance (id, entity_id, observation_id, investigation_id)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (entity_id, observation_id) DO NOTHING
                        """,
                        str(_uuid.uuid4()),
                        entity.id,''')
], need_uuid=False)

fix_file('tests/test_activity_api.py', [
    ('''
            INSERT INTO observations
                (investigation_id, source_adapter, source_version,
                 collected_at, method, target, raw_response,
                 normalized_value, confidence, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            investigation_id,''',
    '''
            INSERT INTO observations
                (id, investigation_id, source_adapter, source_version,
                 collected_at, method, target, raw_response,
                 normalized_value, confidence, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            str(uuid.uuid4()),
            investigation_id,''')
])

fix_file('tests/test_report_architecture.py', [
    ('''
        inv1_id = await conn.fetchval("""
            INSERT INTO investigations (name, target, target_type, status)
            VALUES ('Inv A', 'target_a', 'username', 'active')
            RETURNING id
        """)''',
    '''
        inv1_id = await conn.fetchval("""
            INSERT INTO investigations (id, name, target, target_type, status)
            VALUES ($1, 'Inv A', 'target_a', 'username', 'active')
            RETURNING id
        """, str(uuid.uuid4()))'''),
    ('''
        inv2_id = await conn.fetchval("""
            INSERT INTO investigations (name, target, target_type, status)
            VALUES ('Inv B', 'target_b', 'username', 'completed')
            RETURNING id
        """)''',
    '''
        inv2_id = await conn.fetchval("""
            INSERT INTO investigations (id, name, target, target_type, status)
            VALUES ($1, 'Inv B', 'target_b', 'username', 'completed')
            RETURNING id
        """, str(uuid.uuid4()))''')
])
print('Done!')
