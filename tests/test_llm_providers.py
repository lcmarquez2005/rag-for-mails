from unittest.mock import MagicMock, patch
import pytest

from src.services.ai import (
    LLMService,
    OllamaProvider,
    OpenAIProvider,
    GeminiProvider,
    AnthropicProvider,
    sanitize_json_response,
)
from src.extractor import LLMShiftExtractor, get_extractor


MOCK_RESPONSE_JSON = """{
  "records": [
    {
      "machine_id": "M102",
      "downtime_minutes": 45,
      "approved_parts": 1200,
      "rejected_parts": 15,
      "reasons": ["cambio de molde"],
      "shift_leader": "Juan Pérez",
      "shift": "Turno 1"
    }
  ]
}"""


def test_llm_service_provider_selection():
    # Selección de proveedores y sus alias
    svc_ollama = LLMService(provider="ollama")
    assert isinstance(svc_ollama.provider, OllamaProvider)

    svc_local = LLMService(provider="local")
    assert isinstance(svc_local.provider, OllamaProvider)

    svc_openai = LLMService(provider="openai", api_key="sk-test")
    assert isinstance(svc_openai.provider, OpenAIProvider)

    svc_gemini = LLMService(provider="gemini", api_key="test-gemini-key")
    assert isinstance(svc_gemini.provider, GeminiProvider)

    svc_google = LLMService(provider="google", api_key="test-gemini-key")
    assert isinstance(svc_google.provider, GeminiProvider)

    svc_anthropic = LLMService(provider="anthropic", api_key="test-anthropic-key")
    assert isinstance(svc_anthropic.provider, AnthropicProvider)

    svc_claude = LLMService(provider="claude", api_key="test-anthropic-key")
    assert isinstance(svc_claude.provider, AnthropicProvider)

    with pytest.raises(ValueError, match="no soportado"):
        LLMService(provider="invalid_provider")


def test_openai_provider_generate():
    provider = OpenAIProvider(api_key="sk-mock-key", model="gpt-4o-mini")
    assert provider.is_available() is True

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_RESPONSE_JSON
    mock_client.chat.completions.create.return_value.choices = [mock_choice]
    provider._client = mock_client

    result_raw = provider.generate("texto prueba turno")
    assert "M102" in result_raw
    mock_client.chat.completions.create.assert_called_once()


def test_gemini_provider_generate():
    provider = GeminiProvider(api_key="gemini-mock-key", model="gemini-2.5-flash")
    assert provider.is_available() is True

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = MOCK_RESPONSE_JSON
    mock_client.models.generate_content.return_value = mock_response
    provider._client = mock_client

    result_raw = provider.generate("texto prueba turno")
    assert "M102" in result_raw
    mock_client.models.generate_content.assert_called_once()


def test_anthropic_provider_generate():
    provider = AnthropicProvider(api_key="anthropic-mock-key", model="claude-3-5-sonnet-20240620")
    assert provider.is_available() is True

    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = MOCK_RESPONSE_JSON
    mock_client.messages.create.return_value.content = [mock_block]
    provider._client = mock_client

    result_raw = provider.generate("texto prueba turno")
    assert "M102" in result_raw
    mock_client.messages.create.assert_called_once()


def test_llm_shift_extractor_end_to_end():
    extractor = LLMShiftExtractor(provider="openai", api_key="sk-test")
    # Simular la generación
    with patch.object(extractor.service.provider, "generate", return_value=MOCK_RESPONSE_JSON):
        report = extractor.extract("Texto de turno...")
        assert len(report.records) == 1
        assert report.records[0].machine_id == "M102"
        assert report.records[0].approved_parts == 1200
        assert report.records[0].shift_leader == "Juan Pérez"


def test_get_extractor_factory_with_provider():
    # Force mock siempre retorna MockShiftExtractor
    mock_ext = get_extractor(force_mock=True, provider="openai")
    from src.extractor import MockShiftExtractor
    assert isinstance(mock_ext, MockShiftExtractor)

    # Con API key presente, retorna LLMShiftExtractor
    with patch.object(OpenAIProvider, "is_available", return_value=True):
        llm_ext = get_extractor(force_mock=False, provider="openai")
        assert isinstance(llm_ext, LLMShiftExtractor)
