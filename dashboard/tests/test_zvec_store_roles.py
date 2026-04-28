import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from dashboard.zvec_store import OSTwinStore

@pytest.fixture
def mock_store(tmp_path):
    # Mock zvec to prevent it from trying to open real databases
    with patch("zvec.init"), \
         patch("zvec.open"), \
         patch("zvec.create_and_open"), \
         patch("zvec.CollectionSchema"), \
         patch("zvec.FieldSchema"), \
         patch("zvec.VectorSchema"):
        
        # Set up a fake warrooms dir
        warrooms_dir = tmp_path / "warrooms"
        warrooms_dir.mkdir()
        
        store = OSTwinStore(warrooms_dir)
        # Mock the collections
        store._roles = MagicMock()
        store._embed_available = True
        store._embed_fn = MagicMock()
        store._embed_fn.get_sentence_embedding_dimension.return_value = 384
        
        # Mock _embed_text to return a dummy vector
        store._embed_text = MagicMock(return_value=[0.1] * 384)
        
        return store

def test_index_role_includes_instance_type(mock_store):
    """Verify that index_role correctly passes instance_type to zvec fields."""
    role_id = "test-role-id"
    name = "Test Role"
    description = "A test role description"
    instance_type = "evaluator"
    
    # We need to mock zvec.Doc as well
    with patch("zvec.Doc") as mock_doc_class:
        mock_store.index_role(
            role_id=role_id,
            name=name,
            description=description,
            instance_type=instance_type,
            provider="openai",
            version="gpt-4o"
        )
        
        # Check that zvec.Doc was instantiated with the correct fields
        assert mock_doc_class.called
        args, kwargs = mock_doc_class.call_args
        fields = kwargs.get("fields", {})
        
        assert fields["role_id"] == role_id
        assert fields["name"] == name
        assert fields["description"] == description
        assert fields["instance_type"] == instance_type
        assert fields["provider"] == "openai"
        assert fields["version"] == "gpt-4o"

def test_index_role_default_instance_type(mock_store):
    """Verify that index_role defaults to 'worker' if not specified."""
    role_id = "test-role-worker"
    name = "Worker Role"
    
    with patch("zvec.Doc") as mock_doc_class:
        mock_store.index_role(
            role_id=role_id,
            name=name
        )
        
        assert mock_doc_class.called
        fields = mock_doc_class.call_args[1]["fields"]
        assert fields["instance_type"] == "worker"
