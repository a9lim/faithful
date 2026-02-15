print("VERY START")
import sys
import os

print("Adding path")
sys.path.append(os.getcwd())

print("Importing modules...")
try:
    import asyncio
    import shutil
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock
    
    from faithful.store import MessageStore
    from faithful.backends.markov import MarkovBackend
    from faithful.cogs.chat import Chat
    print("Imports successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

async def test_store_and_backend():
    print("Testing Store and Backend...")
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        # Mock Config
        mock_config = MagicMock()
        mock_config.data_dir = tmp_dir
        
        # Test Store
        store = MessageStore(mock_config)
        # Use longer sentences for state_size=2
        store.add_messages([
            "hello world this is a test", 
            "foo bar baz qux", 
            "python is fun and easy",
            "another long sentence for testing"
        ])
        assert store.count == 4
        print(f"Store added 4 messages. Count: {store.count}")
        
        # Test Remove Last
        removed = store.remove_message(4)
        assert removed == "another long sentence for testing"
        assert store.count == 3
        print(f"Store removed last message. Count: {store.count}")
        
        # Test Backend
        backend = MarkovBackend(mock_config)
        await backend.setup(store.list_messages())
        
        # Test Generation
        response = await backend.generate("hello", store.get_all_text(), [])
        print(f"Markov response to 'hello': {response}")
        
        response_empty = await backend.generate("", store.get_all_text(), [])
        print(f"Markov response to empty prompt: {response_empty}")

    finally:
        shutil.rmtree(tmp_dir)

def test_chat_chunking():
    print("\nTesting Chat Chunking...")
    
    # Mock Bot
    mock_bot = MagicMock()
    mock_bot.config = MagicMock()
    
    chat = Chat(mock_bot)
    
    # Test 1: Simple text
    text = "Hello world"
    chunks = chat._split_into_chunks(text, limit=50)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"
    print("Test 1 passed")
    
    # Test 2: Long text
    text = ("a" * 40) + "\n" + ("b" * 40)
    chunks = chat._split_into_chunks(text, limit=50)
    assert len(chunks) == 2
    assert chunks[0] == "a" * 40
    assert chunks[1] == "b" * 40
    print("Test 2 passed")

async def main():
    await test_store_and_backend()
    test_chat_chunking()
    print("\n✅ All logic checks passed!")

if __name__ == "__main__":
    asyncio.run(main())
