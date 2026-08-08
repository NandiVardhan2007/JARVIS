"""
Comprehensive Unit & Integration Tests for VISION AI API Load Balancer.
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from ai_load_balancer import (
    AIEndpoint,
    AILoadBalancer,
    get_global_balancer,
    LIVEKIT_AVAILABLE,
    LoadBalancedLLM,
)


class TestAIEndpoint(unittest.TestCase):
    def test_endpoint_initialization_and_properties(self):
        ep = AIEndpoint(
            endpoint_id="test_or_1",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1/",
            api_key="sk-or-test-key",
            model="google/gemini-2.0-flash-001",
        )
        self.assertEqual(ep.id, "test_or_1")
        self.assertEqual(ep.provider, "openrouter")
        self.assertEqual(ep.base_url, "https://openrouter.ai/api/v1")
        self.assertFalse(ep.is_cooling_down)

    def test_cooldown_trigger(self):
        ep = AIEndpoint("ep_1", "groq", "https://api.groq.com/openai/v1", "key1", "llama-3")
        ep.trigger_cooldown(seconds=5, reason="Testing rate limit")
        self.assertTrue(ep.is_cooling_down)
        self.assertGreater(ep.cooldown_until, time.time())

    def test_concurrency_and_latency_tracking(self):
        ep = AIEndpoint("ep_2", "nvidia_nim", "https://integrate.api.nvidia.com/v1", "key2", "meta/llama-3")
        self.assertEqual(ep.active_requests, 0)

        ep.record_request_start()
        self.assertEqual(ep.active_requests, 1)

        ep.record_request_end(duration_sec=0.25, success=True)
        self.assertEqual(ep.active_requests, 0)
        self.assertEqual(ep.avg_latency, 0.25)


class TestAILoadBalancer(unittest.TestCase):
    def setUp(self):
        # Set up mock environment variables for online key pools
        os.environ["OPENROUTER_API_KEYS"] = "or-key-1, or-key-2"
        os.environ["NVIDIA_API_KEYS"] = "nim-key-1, nim-key-2"
        os.environ["GROQ_API_KEYS"] = "groq-key-1"

    def test_multi_key_parsing_and_endpoint_pool(self):
        balancer = AILoadBalancer(strategy="least_busy")
        status = balancer.get_status()
        self.assertGreaterEqual(status["total_endpoints"], 5)

        providers = [e["provider"] for e in status["endpoints"]]
        self.assertIn("openrouter", providers)
        self.assertIn("nvidia_nim", providers)
        self.assertIn("groq", providers)

    def test_least_busy_routing(self):
        balancer = AILoadBalancer(strategy="least_busy")
        ep1 = balancer.endpoints[0]
        ep2 = balancer.endpoints[1]

        # Simulate ep1 being busy
        ep1.active_requests = 3
        ep2.active_requests = 0

        selected = balancer.select_endpoint(strategy="least_busy")
        self.assertNotEqual(selected.id, ep1.id)
        self.assertEqual(selected.active_requests, 0)

    def test_round_robin_routing(self):
        balancer = AILoadBalancer(strategy="round_robin")
        selected_1 = balancer.select_endpoint(strategy="round_robin")
        selected_2 = balancer.select_endpoint(strategy="round_robin")
        self.assertNotEqual(selected_1.id, selected_2.id)

    def test_cooldown_exclusion_in_selection(self):
        balancer = AILoadBalancer(strategy="least_busy")
        ep0 = balancer.endpoints[0]
        ep0.trigger_cooldown(seconds=10, reason="Simulated 429 Rate Limit")

        selected = balancer.select_endpoint()
        self.assertNotEqual(selected.id, ep0.id)

    @patch("requests.post")
    def test_chat_completion_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello from load-balanced AI!"}}]
        }
        mock_post.return_value = mock_resp

        balancer = AILoadBalancer()
        output = balancer.chat_completion(
            messages=[{"role": "user", "content": "Hello VISION"}]
        )
        self.assertEqual(output, "Hello from load-balanced AI!")

    @patch("requests.post")
    def test_chat_completion_failover_on_429(self, mock_post):
        # First call returns 429 Rate Limit, second call succeeds 200 OK
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Rate limit exceeded"

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "choices": [{"message": {"content": "Failed over successfully!"}}]
        }

        mock_post.side_effect = [mock_resp_429, mock_resp_200]

        balancer = AILoadBalancer()
        output = balancer.chat_completion(
            messages=[{"role": "user", "content": "Test failover"}]
        )
        self.assertEqual(output, "Failed over successfully!")
        self.assertEqual(mock_post.call_count, 2)

    @patch("requests.post")
    def test_chat_completion_failover_on_402_insufficient_credits(self, mock_post):
        # 402 Insufficient credits triggers 24h cooldown and fails over to next key
        mock_resp_402 = MagicMock()
        mock_resp_402.status_code = 402
        mock_resp_402.text = "User has insufficient credits."

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "choices": [{"message": {"content": "Recovered from 402 credits error!"}}]
        }

        mock_post.side_effect = [mock_resp_402, mock_resp_200]

        balancer = AILoadBalancer()
        ep0 = balancer.endpoints[0]
        output = balancer.chat_completion(
            messages=[{"role": "user", "content": "Test 402 handling"}]
        )
        self.assertEqual(output, "Recovered from 402 credits error!")
        self.assertTrue(ep0.is_cooling_down)
        self.assertGreater(ep0.cooldown_until, time.time() + 80000)

    @patch("requests.post")
    def test_chat_completion_failover_on_401_unauthorized(self, mock_post):
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.text = "Invalid API key"

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "choices": [{"message": {"content": "Recovered from 401 auth error!"}}]
        }

        mock_post.side_effect = [mock_resp_401, mock_resp_200]

        balancer = AILoadBalancer()
        ep0 = balancer.endpoints[0]
        output = balancer.chat_completion(
            messages=[{"role": "user", "content": "Test 401 handling"}]
        )
        self.assertEqual(output, "Recovered from 401 auth error!")
        self.assertTrue(ep0.is_cooling_down)


@unittest.skipUnless(LIVEKIT_AVAILABLE, "LiveKit not available")
class TestLiveKitIntegration(unittest.TestCase):
    def test_load_balanced_llm_instantiation(self):
        balancer = get_global_balancer()
        lk_llm = LoadBalancedLLM(balancer=balancer)
        self.assertIsNotNone(lk_llm)

    def test_load_balanced_llm_chat_kwarg_filtering(self):
        import asyncio
        from livekit.agents import llm

        async def _run():
            balancer = get_global_balancer()
            lk_llm = LoadBalancedLLM(balancer=balancer)
            # Pass 'cache=True' which caused error previously
            stream = lk_llm.chat(chat_ctx=llm.ChatContext(), cache=True)
            self.assertIsNotNone(stream)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
