# update_projects.py
import sqlite3
import json
import random

def update_project_list():
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🔌 Connecting to database...")

    # 1. Clear existing projects
    cursor.execute("DELETE FROM projects")
    print("🗑️  Cleared old project list.")

    # 2. Define the new list from your image
    new_projects = [
        "T-Profile with Cutout",
        "Cutting Exercise",
        "Riveting by Hand",
        "Sandwich",
        "Sheet Metal Shape",
        "Screw Installation",
        "Drill Panel 3/4/5",
        "Third Hand Assembly",
        "Drill Panel 1",
        "Drill Plate Aluminium",
        "Drill Panel 2",
        "Drill Plate Plexiglass",
        "Structure Project",
        "Hi-Lok",
        "Hydraulic Jack Project",
        "SPS- Stabilised Power Supply",
        "FMP - Flap Mechanism Project"
    ]

    # 3. Define some standard tool IDs for simulation
    # (These assume you have tools like 'TW-001', 'MM-001' in your tools table. 
    # If not, the checkout might fail, but the project list will still load.)
    standard_tools = ["TW-001", "MM-001", "CAL-001", "DR-001", "RT-002"]

    # 4. Insert new projects
    print("🚀 Inserting new projects...")
    for i, name in enumerate(new_projects):
        # Create a Project ID (e.g., PROJ-001)
        project_id = f"PROJ-{str(i+1).zfill(3)}"
        
        # Assign a random subset of tools to make it interesting
        # (In real life, you'd specify exactly which tools go with 'Hi-Lok')
        required_tools = json.dumps(random.sample(standard_tools, k=random.randint(2, 4)))
        
        cursor.execute('''
            INSERT INTO projects (id, name, briefing, tool_list)
            VALUES (?, ?, ?, ?)
        ''', (project_id, name, f"Standard operating procedure for {name}", required_tools))

    conn.commit()
    conn.close()
    print(f"✅ SUCCESS: Updated {len(new_projects)} projects.")

if __name__ == "__main__":
    update_project_list()