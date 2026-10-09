from pathlib import Path
import tempfile, unittest
from ai_dlc_mcp.store import MemoryStore

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=MemoryStore(Path(self.tmp.name)/"test.db","ws-test","Test")
        self.store.ensure_project("p1","Project One"); self.store.ensure_project("p2","Project Two")
    def tearDown(self): self.tmp.cleanup()
    def test_project_memory_search_isolated(self):
        self.store.save_memory("p1","constraint","Tenant rule","Every query must include tenant context",["tenant"])
        self.store.save_memory("p2","constraint","Other rule","Use a different partitioning rule",["partition"])
        hits=self.store.search("tenant context","p1"); self.assertTrue(any(h.title=="Tenant rule" for h in hits)); self.assertFalse(any(h.title=="Other rule" for h in hits))
    def test_global_memory_visible(self):
        self.store.save_memory(None,"pattern","Timeout rule","External clients need bounded timeouts",["reliability"])
        self.assertTrue(any(h.title=="Timeout rule" for h in self.store.search("bounded timeouts","p1",True)))
    def test_context_pack(self):
        self.store.save_decision("p1","Messaging","Need async delivery","Use durable queue")
        l=self.store.record_learning("p1","messaging","duplicates","retries","persist idempotency keys",evidence="integration test"); self.store.verify_learning(l["id"],"tester","reproduced by tests/test_idempotency.py::test_duplicate_delivery")
        ctx=self.store.project_context("p1","idempotency"); self.assertIn("Use durable queue",ctx); self.assertIn("persist idempotency keys",ctx)
    def test_rule_approval_guard(self):
        r=self.store.propose_rule("backend","All external clients require timeouts","prevent hangs","p1")
        with self.assertRaises(PermissionError): self.store.review_rule(r["id"],"approve","agent",allow_approval=False)
        self.assertEqual(self.store.review_rule(r["id"],"approve","human",allow_approval=True)["status"],"approved")

if __name__=="__main__": unittest.main()
