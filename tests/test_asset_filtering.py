"""
Test script for the improved asset selection with AI filtering.

This script tests both:
1. Improved prompting for better keyword generation
2. AI-powered filtering of asset options
"""
import asyncio
from utils.assets import search_and_download_asset, search_image, search_video
from utils.ai import gemini_llm_call
from config.prompts import SCRIPT_GENERATOR_SYSTEM


async def test_keyword_generation():
    """Test that the LLM generates better, more visual keywords."""
    print("=" * 60)
    print("TEST 1: Keyword Generation with Improved Prompting")
    print("=" * 60)

    test_article = """
    The stock market soared to new heights today as investors
    celebrated record-breaking gains across multiple sectors.
    """

    user_prompt = f"""
ARTICLE CONTENT:
\"\"\"
{test_article}
\"\"\"
"""

    print("\nGenerating script with improved prompting...")
    script = await gemini_llm_call(
        system_prompt=SCRIPT_GENERATOR_SYSTEM,
        user_prompt=user_prompt,
        json_format=True,
        model_name="gemini-2.5-flash",
    )

    import json
    if isinstance(script, str):
        script = json.loads(script)

    print(f"\n✅ Generated {len(script['scenes'])} scenes")
    print("\nScene Analysis:")
    for scene in script['scenes'][:3]:  # Show first 3 scenes
        print(f"\n  Scene {scene['scene_number']}:")
        print(f"  Script: {scene['script']}")
        print(f"  Keywords: {scene['asset_keywords']}")

    return script


async def test_ai_filtering():
    """Test AI filtering by comparing multiple asset options."""
    print("\n\n" + "=" * 60)
    print("TEST 2: AI-Powered Asset Filtering")
    print("=" * 60)

    # Test with a specific keyword that might have varied results
    test_script = "The market soared to new heights"
    test_keyword = "stock market chart"

    print(f"\n📝 Script: '{test_script}'")
    print(f"🔍 Keyword: '{test_keyword}'")

    # Search for multiple images
    print("\n⏳ Searching Pexels for 5 image options...")
    photo_data = await search_image(test_keyword, orientation="portrait", per_page=5)

    if photo_data.get("photos"):
        photos = photo_data["photos"]
        print(f"✅ Found {len(photos)} images")

        print("\nAvailable options:")
        for i, photo in enumerate(photos):
            print(f"  {i+1}. {photo.get('alt', 'No description')[:80]}...")

        # Test the AI filtering
        from utils.assets import ai_filter_best_asset

        asset_options = [
            {
                "id": photo["id"],
                "alt": photo.get("alt", ""),
                "url": photo.get("url", "")
            }
            for photo in photos
        ]

        print("\n⏳ AI selecting best match...")
        best_index = await ai_filter_best_asset(test_script, asset_options, asset_type="image")

        print(f"\n✅ AI selected option {best_index + 1}:")
        print(f"   {photos[best_index].get('alt', 'No description')}")
        print(f"   URL: {photos[best_index].get('url', '')}")
    else:
        print("❌ No images found")


async def test_full_integration():
    """Test the full integration with actual asset download."""
    print("\n\n" + "=" * 60)
    print("TEST 3: Full Integration Test (with AI filtering)")
    print("=" * 60)

    test_script = "A bustling trading floor with monitors showing rising charts"
    test_keyword = "stock market"

    print(f"\n📝 Script: '{test_script}'")
    print(f"🔍 Keyword: '{test_keyword}'")
    print(f"🎯 AI Filtering: ENABLED")

    try:
        print("\n⏳ Searching and downloading with AI filtering...")
        # This will fetch 5 options and let AI pick the best one
        file_path = await search_and_download_asset(
            keyword=test_keyword,
            asset_type="image",
            file_name="test_ai_filtered",
            script_text=test_script,
            use_ai_filtering=True,
            orientation="portrait",
        )
        print(f"✅ Downloaded: {file_path}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Compare with non-AI filtering
    print(f"\n🎯 AI Filtering: DISABLED (for comparison)")
    try:
        print("⏳ Searching and downloading without AI filtering...")
        file_path = await search_and_download_asset(
            keyword=test_keyword,
            asset_type="image",
            file_name="test_no_ai_filter",
            script_text=test_script,
            use_ai_filtering=False,
            orientation="portrait",
        )
        print(f"✅ Downloaded: {file_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all tests."""
    print("\n🚀 Starting Asset Selection Tests\n")

    try:
        # Test 1: Improved keyword generation
        script = await test_keyword_generation()

        # Test 2: AI filtering
        await test_ai_filtering()

        # Test 3: Full integration
        await test_full_integration()

        print("\n\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
