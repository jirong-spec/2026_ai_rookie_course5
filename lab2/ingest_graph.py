import re, os, sys
from neo4j import GraphDatabase
from tqdm import tqdm

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","password123"))

PATTERNS = [
    (r"^(.+?) works_at (.+?)\.$", ("Person","WORKS_AT","Company")),
    (r"^(.+?) produces (.+?)\.$", ("Company","PRODUCES","Product")),
    (r"^(.+?) partners_with (.+?)\.$", ("Company","PARTNERS_WITH","Company")),
    (r"^(.+?) supplies (.+?) to (.+?)\.$", ("Company","SUPPLIES","Company")),
    (r"^(.+?) leads (.+?)\.$", ("Person","LEADS","Product"))
,
    (r"^(.+?) manages (.+?)\.$", ("Person","MANAGES","Person"))
]

def parse(line:str):
    for pat,(h_l,rel,t_l) in PATTERNS:
        m = re.match(pat,line)
        if m:
            if rel=="SUPPLIES":
                head, item, tail = m.groups()
                return (h_l, head.strip(), rel, t_l, tail.strip(), {"item":item.strip(),"source":line})
            return (h_l, m.group(1).strip(), rel, t_l, m.group(2).strip(), {"source":line})
    return None

def upsert(tx, h_l, h, rel, t_l, t, props):
    tx.run(f"""
        MERGE (h:{h_l}{{name:$h}})
        MERGE (t:{t_l}{{name:$t}})
        MERGE (h)-[r:{rel}]->(t)
        SET r += $props
    """, h=h, t=t, props=props)

with open("docs/data.txt") as f: lines = [l.strip() for l in f if l.strip()]

with driver.session() as session:
    session.run("MATCH (n) DETACH DELETE n")      # reset
    for l in tqdm(lines):
        res = parse(l)
        if res:
            session.execute_write(upsert,*res)
driver.close()
print("Ingestion done.")
