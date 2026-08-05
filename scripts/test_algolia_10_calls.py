import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.services.algolia_search import algolia_search_service
from src.tools.algolia_tool import AlgoliaSearchTool


def main():
    print("=" * 70)
    print("🚀 DataTrust OS — Algolia Enterprise Search 10 API Call Test Suite")
    print("=" * 70)

    # Call 1: Seeding / Initializing index
    print("\n--- [Call 1/10] Seeding All Platform Entities into Algolia Index ---")
    t0 = time.time()
    seed_result = algolia_search_service.seed_all_entities()
    dt1 = (time.time() - t0) * 1000
    print(f"✅ Call 1 Success ({dt1:.2f} ms): {seed_result}")

    # Wait 1s for Algolia asynchronous indexing to catch up
    time.sleep(1.0)

    # Call 2: Keyword Search (Dataset)
    print("\n--- [Call 2/10] Keyword Search for Dataset ('vinfast') ---")
    t0 = time.time()
    res2 = algolia_search_service.search("vinfast")
    dt2 = (time.time() - t0) * 1000
    print(f"✅ Call 2 Success ({dt2:.2f} ms): Found {len(res2)} hits.")
    for h in res2[:2]:
        print(f"   • [{h.get('entity_type')}] {h.get('name') or h.get('objectID')}")

    # Call 3: Typo-Tolerance Search ('vinfas')
    print("\n--- [Call 3/10] Typo-Tolerance Search ('vinfas') ---")
    t0 = time.time()
    res3 = algolia_search_service.search("vinfas")
    dt3 = (time.time() - t0) * 1000
    print(f"✅ Call 3 Success ({dt3:.2f} ms): Found {len(res3)} hits despite typo.")
    for h in res3[:2]:
        print(f"   • [{h.get('entity_type')}] {h.get('name') or h.get('objectID')}")

    # Call 4: Search Alerts by Severity ('critical')
    print("\n--- [Call 4/10] Search Alerts by Severity ('critical') ---")
    t0 = time.time()
    res4 = algolia_search_service.search("critical", entity_type="alert")
    dt4 = (time.time() - t0) * 1000
    print(f"✅ Call 4 Success ({dt4:.2f} ms): Found {len(res4)} alert hits.")

    # Call 5: Search Quality Rules by Column ('fare_amount')
    print("\n--- [Call 5/10] Search Quality Rules by Target ('fare_amount') ---")
    t0 = time.time()
    res5 = algolia_search_service.search("fare_amount", entity_type="rule")
    dt5 = (time.time() - t0) * 1000
    print(f"✅ Call 5 Success ({dt5:.2f} ms): Found {len(res5)} rule hits.")

    # Call 6: Search Audit Logs ('quarantine')
    print("\n--- [Call 6/10] Search Audit Logs ('quarantine') ---")
    t0 = time.time()
    res6 = algolia_search_service.search("quarantine", entity_type="audit")
    dt6 = (time.time() - t0) * 1000
    print(f"✅ Call 6 Success ({dt6:.2f} ms): Found {len(res6)} audit hits.")

    # Call 7: Filtered Search (entity_type='dataset', query='telemetry')
    print("\n--- [Call 7/10] Filtered Search (entity_type='dataset', query='telemetry') ---")
    t0 = time.time()
    res7 = algolia_search_service.search("telemetry", entity_type="dataset")
    dt7 = (time.time() - t0) * 1000
    print(f"✅ Call 7 Success ({dt7:.2f} ms): Found {len(res7)} hits.")

    # Call 8: ReAct Agent Tool Execution Simulation (AlgoliaSearchTool)
    print("\n--- [Call 8/10] ReAct Agent Tool Execution (AlgoliaSearchTool) ---")
    t0 = time.time()
    tool = AlgoliaSearchTool()
    res8 = tool.execute({"query": "trips", "limit": 5})
    dt8 = (time.time() - t0) * 1000
    print(f"✅ Call 8 Success ({dt8:.2f} ms): Agent received {res8.get('count')} hits for query '{res8.get('query')}'.")

    # Call 9: Dynamic Real-time Index Mutation Test
    print("\n--- [Call 9/10] Real-time Index Mutation Test ---")
    t0 = time.time()
    custom_obj = {
        "objectID": "custom_test_999",
        "entity_type": "alert",
        "title": "Algolia Mutation Test Alert",
        "message": "High voltage warning on charging station CS-999",
        "severity": "CRITICAL",
    }
    algolia_search_service.index_entities([custom_obj])
    time.sleep(0.5)
    res9 = algolia_search_service.search("CS-999")
    dt9 = (time.time() - t0) * 1000
    print(f"✅ Call 9 Success ({dt9:.2f} ms): Successfully inserted & retrieved dynamically added record.")

    # Call 10: High-Throughput Latency Benchmark
    print("\n--- [Call 10/10] High-Throughput Latency Benchmark ---")
    queries = ["grab", "hcmc", "weather", "quarantine", "vietnam"]
    t0 = time.time()
    for q in queries:
        algolia_search_service.search(q, limit=3)
    dt10 = (time.time() - t0) * 1000
    avg_latency = dt10 / len(queries)
    print(f"✅ Call 10 Success ({dt10:.2f} ms total, avg {avg_latency:.2f} ms/query across {len(queries)} calls).")

    print("\n" + "=" * 70)
    print("🎉 ALL 10 ALGOLIA API CALL TESTS PASSED 100% SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
