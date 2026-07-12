"""Quick diagnostic: Mem0 long-term + PostgresSaver short-term memory."""

import asyncio
import sys
import uuid

from main import (
    app,
    build_input_state,
    build_run_config,
    load_user_plan,
    memory_manager,
    state_to_plan_dict,
)


TEST_USER = "memtest_" + uuid.uuid4().hex[:8]


async def test_mem0_long_term() -> bool:
    print("\n=== TEST 1: Mem0 Long-Term Memory ===")
    fact = "I am vegetarian and prefer direct flights for all trips."
    query = "Plan a trip to Japan"

    try:
        # Write
        add_result = await memory_manager._provider.add_fact(TEST_USER, fact)
        print("ADD result:", add_result)

        # Small delay for Mem0 indexing
        await asyncio.sleep(3)

        # Read
        items = await memory_manager.retrieve_memories(TEST_USER, query)
        context = memory_manager.format_memories_for_prompt(items)

        print(f"Retrieved {len(items)} memories for user '{TEST_USER}':")
        for item in items:
            print(f"  - {item.memory[:120]}")

        ok = any(
            "vegetarian" in item.memory.lower() or "direct" in item.memory.lower()
            for item in items
        ) or "vegetarian" in context.lower()

        if ok:
            print("RESULT: PASS - Mem0 long-term memory is working")
        else:
            print("RESULT: WARN - Add succeeded but search did not return expected fact yet")
            print("Context:", context[:300])
        return ok
    except Exception as exc:
        print(f"RESULT: FAIL - Mem0 error: {exc}")
        return False


async def test_postgres_short_term() -> bool:
    print("\n=== TEST 2: PostgresSaver Short-Term Memory ===")
    thread_id = memory_manager.build_thread_id(TEST_USER, "diagnostic")
    config = build_run_config(user_id=TEST_USER, session_id=thread_id)

    marker_query = f"Diagnostic trip to Lisbon - marker {uuid.uuid4().hex[:6]}"
    input_state = build_input_state(marker_query, user_id=TEST_USER, session_id=thread_id)

    try:
        # Write minimal checkpoint via graph start (retrieve_memory only - fast)
        result = await app.ainvoke(
            input_state,
            config=config,
        )
        itinerary = result.get("itinerary", "")
        print(f"Graph completed. Itinerary length: {len(itinerary)}")

        # Read back from checkpoint
        snapshot = app.get_state(config)
        restored = snapshot.values if snapshot else {}
        restored_query = restored.get("user_query", "")
        restored_itinerary = restored.get("itinerary", "")

        print(f"Checkpoint user_query: {restored_query[:80]}...")
        print(f"Checkpoint itinerary length: {len(restored_itinerary)}")

        plan = load_user_plan(TEST_USER, thread_id)
        plan_ok = plan is not None and marker_query in plan.get("user_query", "")

        if plan_ok:
            print("RESULT: PASS - PostgresSaver short-term checkpoint is working")
            print(f"  Destination from plan: {plan.get('destination', 'N/A')}")
        else:
            print("RESULT: FAIL - Could not restore plan from checkpoint")
            print(f"  Expected query containing: {marker_query}")
            print(f"  Got: {restored_query}")

        return plan_ok
    except Exception as exc:
        print(f"RESULT: FAIL - PostgresSaver error: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("Memory diagnostic for Voyager AI")
    print(f"Test user_id: {TEST_USER}")

    mem0_ok = await test_mem0_long_term()

    # Full graph test takes several minutes - offer lighter checkpoint test first
    print("\nNote: Short-term test runs the FULL agent graph (may take 2-5 min)...")
    short_ok = await test_postgres_short_term()

    print("\n=== SUMMARY ===")
    print(f"Mem0 (long-term):     {'PASS' if mem0_ok else 'FAIL'}")
    print(f"Postgres (short-term): {'PASS' if short_ok else 'FAIL'}")

    if mem0_ok and short_ok:
        print("\nBoth memory systems are working.")
        return 0
    print("\nOne or more tests failed — see details above.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
