from neo4j import GraphDatabase
import os

NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'neo4j')

_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def close():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def _run_write(fn, *args, **kwargs):
    d = driver()
    with d.session() as sess:
        return sess.write_transaction(lambda tx: fn(tx, *args, **kwargs))


def bulk_write(nodes, links):
    """Write nodes and links to Neo4j using UNWIND for efficient import.

    nodes: list of {id, label, category, definition?}
    links: list of {source, target, weight, source_name?}
    """

    def _write_nodes(tx, nodes_):
        tx.run(
            """
            UNWIND $nodes AS n
            MERGE (c:Concept {id: n.id})
            SET c.label = n.label, c.category = coalesce(n.category, 'unknown'), c.definition = coalesce(n.definition, ''), c.updated_at = datetime() 
            """,
            nodes=nodes_
        )

    def _write_links(tx, links_):
        tx.run(
            """
            UNWIND $links AS l
            MATCH (a:Concept {id: l.source}), (b:Concept {id: l.target})
            MERGE (a)-[r:RELATED_TO]->(b)
            SET r.weight = coalesce(r.weight,0) + coalesce(l.weight,1), r.source = coalesce(l.source, 'batch')
            """,
            links=links_
        )

    # perform writes
    _run_write(_write_nodes, nodes)
    _run_write(_write_links, links)


def fetch_graph(limit=1000):
    """Fetch a simple projection of the graph for frontend consumption."""
    d = driver()
    with d.session() as sess:
        q = (
            "MATCH (n:Concept)-[r:RELATED_TO]->(m:Concept)"
            " RETURN n.id AS n_id, n.label AS n_label, n.category AS n_cat, m.id AS m_id, m.label AS m_label, r.weight AS weight"
            " LIMIT $limit"
        )
        res = sess.run(q, limit=limit)
        nodes = {}
        links = []
        for rec in res:
            n_id = rec['n_id']
            m_id = rec['m_id']
            if n_id not in nodes:
                nodes[n_id] = {'id': n_id, 'label': rec.get('n_label') or n_id, 'category': rec.get('n_cat')}
            if m_id not in nodes:
                nodes[m_id] = {'id': m_id, 'label': rec.get('m_label') or m_id}
            links.append({'source': n_id, 'target': m_id, 'weight': rec.get('weight') or 1})

        return {'nodes': list(nodes.values()), 'links': links}


    def fetch_node(node_id):
        d = driver()
        with d.session() as sess:
            q = (
                "MATCH (n:Concept {id: $id})"
                " RETURN n LIMIT 1"
            )
            res = sess.run(q, id=node_id)
            rec = res.single()
            if not rec:
                return None
            n = rec['n']
            props = dict(n)
            props['id'] = node_id
            return props


    def update_node_status(node_id, props: dict):
        """Set properties on a node identified by id."""
        def _update(tx, nid, p):
            set_clause = ', '.join([f"n.{k} = $p.{k}" for k in p.keys()])
            # build dynamic cypher with parameters
            cy = f"MATCH (n:Concept {{id: $id}}) SET {set_clause} RETURN n"
            tx.run(cy, id=nid, p=p)

        _run_write(lambda tx, nid, p: _update(tx, nid, p), node_id, props)


    def fetch_nodes_by_status(status: str = 'final', limit: int = 1000):
        """Fetch node ids with a given status."""
        d = driver()
        with d.session() as sess:
            q = (
                "MATCH (n:Concept) WHERE coalesce(n.status,'') = $status RETURN n.id AS id, n.label AS label LIMIT $limit"
            )
            res = sess.run(q, status=status, limit=limit)
            out = []
            for r in res:
                out.append({'id': r['id'], 'label': r.get('label')})
            return out
