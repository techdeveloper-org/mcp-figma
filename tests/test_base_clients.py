"""Tests for base/clients.py - LazyClient, GitRepoClient, GitHubApiClient, etc.

Covers LazyClient singleton, lazy init, get(), get_or_raise(), available property,
reset(), reset_all(), health_check(), GitRepoClient.for_path (import error case),
GitHubApiClient._resolve_token, _parse_remote, EmbeddingManager.embed, and
QdrantManager._health_check.

ASCII-only (cp1252 safe).
"""
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from base.clients import (
    LazyClient,
    GitRepoClient,
    GitHubApiClient,
    QdrantManager,
    EmbeddingManager,
)


# ---------------------------------------------------------------------------
# Concrete minimal LazyClient for testing the abstract base
# ---------------------------------------------------------------------------

class AlwaysGoodClient(LazyClient):
    """Concrete LazyClient that always initialises to a sentinel string."""

    def _initialize(self):
        return "initialized_resource"


class AlwaysFailClient(LazyClient):
    """Concrete LazyClient whose _initialize() always raises."""

    def _initialize(self):
        raise RuntimeError("init failed")


class NoneReturningClient(LazyClient):
    """Concrete LazyClient whose _initialize() returns None."""

    def _initialize(self):
        return None


class HealthyClient(LazyClient):
    """Concrete LazyClient that provides extra health data."""

    def _initialize(self):
        return "ok"

    def _health_check(self):
        return {"extra": "data"}


class DegradedHealthClient(LazyClient):
    """Concrete LazyClient whose _health_check() raises."""

    def _initialize(self):
        return "ok"

    def _health_check(self):
        raise RuntimeError("health check broken")


# ---------------------------------------------------------------------------
# LazyClient - Singleton and basic lifecycle
# ---------------------------------------------------------------------------

class TestLazyClientSingleton:
    """Tests for LazyClient.instance() singleton pattern."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_instance_returns_same_object(self):
        a = AlwaysGoodClient.instance()
        b = AlwaysGoodClient.instance()
        assert a is b

    def test_different_subclasses_get_different_singletons(self):
        a = AlwaysGoodClient.instance()
        b = AlwaysFailClient.instance()
        assert a is not b

    def test_reset_all_clears_registry(self):
        a = AlwaysGoodClient.instance()
        LazyClient.reset_all()
        b = AlwaysGoodClient.instance()
        assert a is not b

    def test_reset_all_resets_client_state(self):
        c = AlwaysGoodClient.instance()
        c.get()
        LazyClient.reset_all()
        fresh = AlwaysGoodClient.instance()
        assert fresh._client is None


class TestLazyClientGet:
    """Tests for LazyClient.get() lazy initialisation."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_get_returns_initialized_resource(self):
        c = AlwaysGoodClient.instance()
        assert c.get() == "initialized_resource"

    def test_get_returns_same_object_on_second_call(self):
        c = AlwaysGoodClient.instance()
        r1 = c.get()
        r2 = c.get()
        assert r1 is r2

    def test_get_returns_none_when_init_raises(self):
        c = AlwaysFailClient.instance()
        assert c.get() is None

    def test_get_stores_error_when_init_raises(self):
        c = AlwaysFailClient.instance()
        c.get()
        assert "init failed" in c._error

    def test_get_sets_available_false_on_failure(self):
        c = AlwaysFailClient.instance()
        c.get()
        assert c._available is False

    def test_get_returns_none_when_init_returns_none(self):
        c = NoneReturningClient.instance()
        assert c.get() is None
        assert c._available is False


class TestLazyClientGetOrRaise:
    """Tests for get_or_raise()."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_get_or_raise_returns_resource(self):
        c = AlwaysGoodClient.instance()
        assert c.get_or_raise() == "initialized_resource"

    def test_get_or_raise_raises_runtime_error_on_failure(self):
        c = AlwaysFailClient.instance()
        with pytest.raises(RuntimeError, match="not available"):
            c.get_or_raise()

    def test_get_or_raise_includes_class_name(self):
        c = AlwaysFailClient.instance()
        with pytest.raises(RuntimeError) as exc_info:
            c.get_or_raise()
        assert "AlwaysFailClient" in str(exc_info.value)


class TestLazyClientAvailableProperty:
    """Tests for the available property."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_available_true_when_initialized(self):
        c = AlwaysGoodClient.instance()
        assert c.available is True

    def test_available_false_when_init_fails(self):
        c = AlwaysFailClient.instance()
        assert c.available is False

    def test_available_triggers_initialization(self):
        c = AlwaysGoodClient.instance()
        assert c._client is None
        _ = c.available
        assert c._client is not None


class TestLazyClientReset:
    """Tests for reset() per-instance method."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_reset_clears_client(self):
        c = AlwaysGoodClient.instance()
        c.get()
        c.reset()
        assert c._client is None

    def test_reset_clears_error(self):
        c = AlwaysFailClient.instance()
        c.get()
        c.reset()
        assert c._error is None

    def test_reset_clears_available(self):
        c = AlwaysGoodClient.instance()
        c.get()
        c.reset()
        assert c._available is False

    def test_get_reinitializes_after_reset(self):
        c = AlwaysGoodClient.instance()
        c.get()
        c.reset()
        assert c.get() == "initialized_resource"


class TestLazyClientHealthCheck:
    """Tests for health_check()."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_health_check_unavailable_client(self):
        c = AlwaysFailClient.instance()
        result = c.health_check()
        assert result["available"] is False
        assert result["status"] == "unavailable"
        assert "error" in result

    def test_health_check_available_client(self):
        c = AlwaysGoodClient.instance()
        result = c.health_check()
        assert result["available"] is True
        assert result["status"] == "healthy"

    def test_health_check_includes_extra_data(self):
        c = HealthyClient.instance()
        result = c.health_check()
        assert result.get("extra") == "data"

    def test_health_check_degraded_when_health_check_raises(self):
        c = DegradedHealthClient.instance()
        result = c.health_check()
        assert result["status"] == "degraded"
        assert "health_error" in result


# ---------------------------------------------------------------------------
# GitRepoClient
# ---------------------------------------------------------------------------

class TestGitRepoClient:
    """Tests for GitRepoClient.for_path() import-error handling."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_for_path_raises_runtime_error_when_gitpython_missing(self):
        with patch.dict("sys.modules", {"git": None}):
            with pytest.raises(RuntimeError, match="GitPython not installed"):
                GitRepoClient.for_path(".")

    def test_initialize_raises_runtime_error_when_gitpython_missing(self):
        with patch.dict("sys.modules", {"git": None}):
            c = GitRepoClient.instance()
            c.get()
            assert c._error is not None

    def test_for_path_returns_repo_when_gitpython_available(self):
        mock_repo = MagicMock()
        mock_git = MagicMock()
        mock_git.Repo.return_value = mock_repo
        with patch.dict("sys.modules", {"git": mock_git}):
            result = GitRepoClient.for_path(".")
        assert result is mock_repo

    def test_health_check_returns_none_when_no_client(self):
        c = GitRepoClient()
        assert c._health_check() is None


# ---------------------------------------------------------------------------
# GitHubApiClient
# ---------------------------------------------------------------------------

class TestGitHubApiClient:
    """Tests for GitHubApiClient token resolution and remote parsing."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_resolve_token_reads_from_env(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env_token"}):
            token = GitHubApiClient._resolve_token()
        assert token == "env_token"

    def test_resolve_token_falls_back_to_gh_cli(self):
        import subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "cli_token\n"
        env_without_token = {k: v for k, v in __import__("os").environ.items()
                             if k != "GITHUB_TOKEN"}
        with patch.dict("os.environ", env_without_token, clear=True):
            with patch("subprocess.run", return_value=mock_result):
                token = GitHubApiClient._resolve_token()
        assert token == "cli_token"

    def test_resolve_token_returns_none_when_gh_not_found(self):
        env_without_token = {k: v for k, v in __import__("os").environ.items()
                             if k != "GITHUB_TOKEN"}
        with patch.dict("os.environ", env_without_token, clear=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                token = GitHubApiClient._resolve_token()
        assert token is None

    def test_resolve_token_returns_none_when_gh_fails(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        env_without_token = {k: v for k, v in __import__("os").environ.items()
                             if k != "GITHUB_TOKEN"}
        with patch.dict("os.environ", env_without_token, clear=True):
            with patch("subprocess.run", return_value=mock_result):
                token = GitHubApiClient._resolve_token()
        assert token is None

    def test_parse_remote_ssh_format(self):
        mock_repo = MagicMock()
        mock_repo.remotes.origin.url = "git@github.com:owner/repo.git"
        with patch("git.Repo", return_value=mock_repo):
            owner, name = GitHubApiClient._parse_remote(".")
        assert owner == "owner"
        assert name == "repo"

    def test_parse_remote_https_format(self):
        mock_repo = MagicMock()
        mock_repo.remotes.origin.url = "https://github.com/owner/myrepo.git"
        with patch("git.Repo", return_value=mock_repo):
            owner, name = GitHubApiClient._parse_remote(".")
        assert owner == "owner"
        assert name == "myrepo"

    def test_parse_remote_non_github_returns_none(self):
        mock_repo = MagicMock()
        mock_repo.remotes.origin.url = "https://gitlab.com/owner/repo.git"
        with patch("git.Repo", return_value=mock_repo):
            owner, name = GitHubApiClient._parse_remote(".")
        assert owner is None
        assert name is None

    def test_parse_remote_returns_none_on_import_error(self):
        with patch.dict("sys.modules", {"git": None}):
            owner, name = GitHubApiClient._parse_remote(".")
        assert owner is None
        assert name is None

    def test_initialize_raises_runtime_error_without_token(self):
        env_without = {k: v for k, v in __import__("os").environ.items()
                       if k != "GITHUB_TOKEN"}
        mock_github = MagicMock()
        with patch.dict("os.environ", env_without, clear=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch.dict("sys.modules", {"github": mock_github}):
                    c = GitHubApiClient.instance()
                    c.get()
        assert c._error is not None

    def test_initialize_raises_when_pygithub_missing(self):
        with patch.dict("sys.modules", {"github": None}):
            c = GitHubApiClient.instance()
            c.get()
        assert "PyGithub not installed" in (c._error or "")

    def test_get_repo_raises_when_cannot_detect_remote(self):
        c = GitHubApiClient.instance()
        c._client = MagicMock()
        c._available = True
        with patch.object(GitHubApiClient, "_parse_remote", return_value=(None, None)):
            with pytest.raises(RuntimeError, match="Cannot detect GitHub repo"):
                c.get_repo(".")


# ---------------------------------------------------------------------------
# EmbeddingManager
# ---------------------------------------------------------------------------

class TestEmbeddingManager:
    """Tests for EmbeddingManager.embed()."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_embed_raises_when_model_unavailable(self):
        c = EmbeddingManager.instance()
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            c._client = None
            c._available = False
            c._error = None
            with pytest.raises(RuntimeError):
                c.embed("hello")

    def test_embed_calls_model_encode(self):
        c = EmbeddingManager.instance()
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2])
        c._client = mock_model
        c._available = True
        result = c.embed("test text")
        mock_model.encode.assert_called_once_with("test text", normalize_embeddings=True)

    def test_health_check_returns_model_info(self):
        c = EmbeddingManager.instance()
        info = c._health_check()
        assert info["model"] == EmbeddingManager.MODEL_NAME
        assert info["dimension"] == EmbeddingManager.DIMENSION

    def test_initialize_raises_when_sentence_transformers_missing(self):
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            c = EmbeddingManager.instance()
            c.get()
        assert c._error is not None


# ---------------------------------------------------------------------------
# QdrantManager
# ---------------------------------------------------------------------------

class TestQdrantManager:
    """Tests for QdrantManager._health_check()."""

    def setup_method(self):
        LazyClient.reset_all()

    def test_health_check_returns_none_when_no_client(self):
        c = QdrantManager()
        assert c._health_check() is None

    def test_health_check_returns_collection_status(self):
        c = QdrantManager.instance()
        mock_client = MagicMock()
        mock_info = MagicMock()
        mock_info.status = "green"
        mock_info.points_count = 10
        mock_client.get_collection.return_value = mock_info
        c._client = mock_client
        c._available = True

        result = c._health_check()

        assert "collections" in result
        for name in QdrantManager.COLLECTIONS:
            assert name in result["collections"]

    def test_health_check_handles_collection_error(self):
        c = QdrantManager.instance()
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("unavailable")
        c._client = mock_client
        c._available = True

        result = c._health_check()

        for name in QdrantManager.COLLECTIONS:
            assert result["collections"][name]["status"] == "ERROR"

    def test_get_db_path_returns_path(self):
        path = QdrantManager._get_db_path()
        assert "vector_db" in str(path)

    @pytest.mark.unit
    def test_initialize_creates_collections_with_mocked_qdrant(self):
        """QdrantManager._initialize() creates collections via mocked QdrantClient."""
        mock_client = MagicMock()
        mock_collection_list = MagicMock()
        mock_collection_list.collections = []
        mock_client.get_collections.return_value = mock_collection_list

        mock_qdrant_module = MagicMock()
        mock_qdrant_module.QdrantClient.return_value = mock_client
        mock_models = MagicMock()
        mock_models.Distance.COSINE = "Cosine"
        mock_models.VectorParams = MagicMock(return_value=MagicMock())

        import sys
        from unittest.mock import patch
        with patch.dict(sys.modules, {
            "qdrant_client": mock_qdrant_module,
            "qdrant_client.models": mock_models,
        }):
            with patch.object(QdrantManager, "_get_db_path") as mock_path:
                import pathlib
                mock_path.return_value = MagicMock(spec=pathlib.Path)
                mock_path.return_value.mkdir = MagicMock()
                mock_path.return_value.__str__ = MagicMock(return_value="/tmp/qdrant_test")

                c = QdrantManager()
                result = c._initialize()

        assert result is mock_client
        mock_client.create_collection.assert_called()

    @pytest.mark.unit
    def test_initialize_skips_existing_collections(self):
        """_initialize() skips create_collection when collection already exists (474->473 False)."""
        mock_client = MagicMock()

        existing_names = list(QdrantManager.COLLECTIONS.keys())
        mock_coll = MagicMock()
        mock_coll.name = existing_names[0]
        mock_collection_list = MagicMock()
        mock_collection_list.collections = [MagicMock(name=n) for n in existing_names]
        for i, n in enumerate(existing_names):
            mock_collection_list.collections[i].name = n
        mock_client.get_collections.return_value = mock_collection_list

        mock_qdrant_module = MagicMock()
        mock_qdrant_module.QdrantClient.return_value = mock_client
        mock_models = MagicMock()
        mock_models.Distance.COSINE = "Cosine"
        mock_models.VectorParams = MagicMock(return_value=MagicMock())

        import sys
        from unittest.mock import patch
        with patch.dict(sys.modules, {
            "qdrant_client": mock_qdrant_module,
            "qdrant_client.models": mock_models,
        }):
            with patch.object(QdrantManager, "_get_db_path") as mock_path:
                import pathlib
                mock_path.return_value = MagicMock(spec=pathlib.Path)
                mock_path.return_value.mkdir = MagicMock()
                mock_path.return_value.__str__ = MagicMock(return_value="/tmp/qdrant_test2")

                c = QdrantManager()
                result = c._initialize()

        assert result is mock_client
        mock_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# Coverage gap: LazyClient.error property (line 142)
# ---------------------------------------------------------------------------

class TestLazyClientErrorProperty:
    """Tests for the LazyClient.error property accessor (line 142)."""

    def setup_method(self):
        LazyClient.reset_all()

    @pytest.mark.unit
    def test_error_property_returns_none_before_init(self):
        """error property returns None before any initialization attempt."""
        c = AlwaysGoodClient.instance()
        assert c.error is None

    @pytest.mark.unit
    def test_error_property_returns_message_after_failure(self):
        """error property returns the failure message after a failed initialization."""
        c = AlwaysFailClient.instance()
        c.get()
        assert c.error == "init failed"

    @pytest.mark.unit
    def test_error_property_returns_none_after_success(self):
        """error property returns None after successful initialization."""
        c = AlwaysGoodClient.instance()
        c.get()
        assert c.error is None


# ---------------------------------------------------------------------------
# Coverage gap: GitRepoClient._health_check with active client (lines 281, 294)
# ---------------------------------------------------------------------------

class TestGitRepoClientHealthCheck:
    """Tests for GitRepoClient._health_check() with an active client."""

    def setup_method(self):
        LazyClient.reset_all()

    @pytest.mark.unit
    def test_health_check_returns_branch_info_when_client_active(self):
        """_health_check returns branch and is_dirty when _client is set."""
        c = GitRepoClient()
        mock_repo = MagicMock()
        mock_repo.active_branch.__str__ = MagicMock(return_value="main")
        mock_repo.is_dirty.return_value = False
        c._client = mock_repo
        c._available = True

        result = c._health_check()

        assert result is not None
        assert "branch" in result
        assert "is_dirty" in result
        assert result["is_dirty"] is False


# ---------------------------------------------------------------------------
# Coverage gap: GitHubApiClient._initialize with token + PyGithub (line 338)
# and get_repo when remote parses (line 389)
# and _parse_remote when parts < 2 (line 416)
# ---------------------------------------------------------------------------

class TestGitHubApiClientInitialize:
    """Tests for GitHubApiClient._initialize() and get_repo()."""

    def setup_method(self):
        LazyClient.reset_all()

    @pytest.mark.unit
    def test_initialize_returns_github_instance_when_token_and_module_available(self):
        """_initialize returns a Github client whose retry policy excludes POST.

        PyGithub's default GithubRetry retries POST, so a lost response on a
        create call would file a duplicate resource. The client must therefore
        pass an explicit retry policy restricted to idempotent methods.
        """
        mock_gh_instance = MagicMock()
        mock_github_module = MagicMock()
        mock_github_module.Github.return_value = mock_gh_instance
        mock_retry_module = MagicMock()

        with patch.dict("os.environ", {"GITHUB_TOKEN": "test_tok"}):
            with patch.dict(
                "sys.modules",
                {
                    "github": mock_github_module,
                    "github.GithubRetry": mock_retry_module,
                },
            ):
                c = GitHubApiClient.instance()
                result = c._initialize()

        assert result is mock_gh_instance
        call = mock_github_module.Github.call_args
        assert call.args[0] == "test_tok"
        assert "retry" in call.kwargs

        retry_kwargs = mock_retry_module.GithubRetry.call_args.kwargs
        allowed = set(retry_kwargs["allowed_methods"])
        assert "POST" not in allowed
        assert "GET" in allowed

    @pytest.mark.unit
    def test_get_repo_returns_repo_when_remote_parsed(self):
        """get_repo returns client.get_repo() when owner/name are detected."""
        c = GitHubApiClient.instance()
        mock_gh_client = MagicMock()
        expected_repo = MagicMock()
        mock_gh_client.get_repo.return_value = expected_repo
        c._client = mock_gh_client
        c._available = True

        with patch.object(GitHubApiClient, "_parse_remote", return_value=("owner", "myrepo")):
            result = c.get_repo(".")

        assert result is expected_repo
        mock_gh_client.get_repo.assert_called_once_with("owner/myrepo")

    @pytest.mark.unit
    def test_parse_remote_returns_none_when_parts_fewer_than_2(self):
        """_parse_remote returns (None, None) when SSH URL has fewer than 2 path parts."""
        mock_repo = MagicMock()
        mock_repo.remotes.origin.url = "git@github.com:single-part.git"
        with patch("git.Repo", return_value=mock_repo):
            owner, name = GitHubApiClient._parse_remote(".")
        assert owner is None or name is None


# ---------------------------------------------------------------------------
# Coverage gap: GitRepoClient._initialize success path (line 281)
# ---------------------------------------------------------------------------

class TestGitRepoClientInitialize:
    """Tests for GitRepoClient._initialize() success path."""

    def setup_method(self):
        LazyClient.reset_all()

    @pytest.mark.unit
    def test_initialize_returns_repo_when_git_available(self):
        """_initialize() returns a Repo instance when git module and path are valid."""
        mock_repo_instance = MagicMock()
        mock_git = MagicMock()
        mock_git.Repo.return_value = mock_repo_instance

        with patch.dict("sys.modules", {"git": mock_git}):
            c = GitRepoClient.instance()
            result = c._initialize()

        assert result is mock_repo_instance
        mock_git.Repo.assert_called_once_with(".")


# ---------------------------------------------------------------------------
# Coverage gap: EmbeddingManager._initialize success path (line 533)
# ---------------------------------------------------------------------------

class TestEmbeddingManagerInitialize:
    """Tests for EmbeddingManager._initialize() success path."""

    def setup_method(self):
        LazyClient.reset_all()

    @pytest.mark.unit
    def test_initialize_returns_model_when_sentence_transformers_available(self):
        """_initialize() returns a SentenceTransformer when the package is importable."""
        mock_model = MagicMock()
        mock_st_module = MagicMock()
        mock_st_module.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            from base.clients import EmbeddingManager
            c = EmbeddingManager()
            result = c._initialize()

        assert result is mock_model
        mock_st_module.SentenceTransformer.assert_called_once()
