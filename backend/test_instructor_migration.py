import asyncio
from intelligence.voc_synthesis import batch_prescore_posts
from core.gemini_client import GeminiClient

async def test():
    gemini_client = GeminiClient()

    test_posts = [
        {
            "id": "test1",
            "title": "HR automation tools",
            "content": "Looking for HR automation solutions",
        },
        {
            "id": "test2",
            "title": "Cats are cute",
            "content": "I love cats",
        }
    ]

    config = {
        "audience": "Enterprise HR teams",
        "priorities": ["HR automation", "talent acquisition"]
    }

    results, warnings = await batch_prescore_posts(
        test_posts, config, "Enterprise HR", gemini_client
    )

    print(f"Success: {len(results)}/2")
    print(f"Warnings: {warnings}")
    for r in results:
        print(f"Post {r['id']}: {r['prescore']}")

asyncio.run(test())