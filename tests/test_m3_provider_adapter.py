"""Offline extraction seam, cooperative timeout and privacy regressions."""
from dataclasses import replace
import unittest
from unittest.mock import patch
import circuit_image as ci
from tests.m3c_helpers import fixture_image, envelope, encode, REPLAYS


class FakeProvider:
    info=ci.STATIC_PROVIDER
    def __init__(self,payload=None,error=None,info=None):
        self.payload,self.error,self.calls=payload,error,0
        if info is not None: self.info=info
    def extract(self,image,*,timeout_s):
        self.calls+=1
        self.image,self.timeout=image,timeout_s
        if self.error: raise self.error
        return self.payload


class ProviderAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.image=fixture_image()

    def test_static_replay_deterministic_and_not_a_model(self):
        provider=ci.StaticReplayProvider(encode(envelope(self.image)))
        a,b=ci.extract_observations(self.image,provider),ci.extract_observations(self.image,provider)
        self.assertEqual(a,b)
        self.assertEqual(a.status,"SUCCESS")
        self.assertEqual(a.observation_set.provider.provider_id,"static-replay")
        self.assertIsNone(a.observation_set.provider.model_id)
        self.assertIsNone(a.observation_set.provider.model_version)
        self.assertNotIn("payload=",repr(provider))

    def test_supplied_bytes_no_network_or_filesystem(self):
        provider=ci.StaticReplayProvider((REPLAYS/"divider_partial.json").read_bytes())
        with patch("builtins.open",side_effect=AssertionError("filesystem")),patch("socket.socket",side_effect=AssertionError("network")),patch("subprocess.Popen",side_effect=AssertionError("process")):
            result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.status,"INCOMPLETE")

    def test_provider_unavailable(self):
        provider=FakeProvider(error=ci.ProviderUnavailable("private diagnostic text"))
        result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.diagnostics[0].code,"PROVIDER_UNAVAILABLE")
        self.assertIsNone(result.observation_set)
        self.assertNotIn("private",repr(result))

    def test_provider_timeout_exception(self):
        result=ci.extract_observations(self.image,FakeProvider(error=TimeoutError("private")))
        self.assertEqual(result.diagnostics[0].code,"PROVIDER_TIMEOUT")
        self.assertIsNone(result.observation_set)

    def test_late_cooperative_return_is_failure(self):
        provider=FakeProvider(encode(envelope(self.image)))
        with patch("circuit_image.providers.monotonic",side_effect=(100,103)):
            result=ci.extract_observations(self.image,provider,timeout_s=2)
        self.assertEqual(result.diagnostics[0].code,"PROVIDER_TIMEOUT")
        self.assertEqual(provider.calls,1)
        self.assertEqual(provider.timeout,2.0)

    def test_provider_exception_sanitized_no_retry(self):
        provider=FakeProvider(error=ConnectionError("credential or image content"))
        result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.diagnostics[0].code,"PROVIDER_FAILED")
        self.assertNotIn("credential",repr(result))
        self.assertEqual(provider.calls,1)

    def test_missing_provider_interface(self):
        self.assertEqual(ci.extract_observations(self.image,object()).diagnostics[0].code,"PROVIDER_FAILED")

    def test_remote_disabled_before_callback(self):
        remote=replace(ci.STATIC_PROVIDER,provider_id="future-provider",mode="remote",model_id="unknown")
        provider=FakeProvider(info=remote)
        result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.diagnostics[0].code,"PROVIDER_REMOTE_DISABLED")
        self.assertEqual(provider.calls,0)

    def test_local_inference_not_enabled(self):
        provider=FakeProvider(info=replace(ci.STATIC_PROVIDER,provider_id="future-local",mode="local"))
        self.assertEqual(ci.extract_observations(self.image,provider).diagnostics[0].code,"PROVIDER_UNAVAILABLE")
        self.assertEqual(provider.calls,0)

    def test_malformed_response(self):
        result=ci.extract_observations(self.image,ci.StaticReplayProvider(b'{"bad":'))
        self.assertEqual(result.status,"FAILED")
        self.assertEqual(result.diagnostics[0].code,"OBS_JSON_INVALID")

    def test_incompatible_response_version(self):
        data=envelope(self.image); data["version"]="future"
        result=ci.extract_observations(self.image,ci.StaticReplayProvider(encode(data)))
        self.assertEqual(result.diagnostics[0].code,"OBS_VERSION_UNSUPPORTED")

    def test_incomplete_and_empty_observations(self):
        data=envelope(self.image,[],coverage="partial")
        result=ci.extract_observations(self.image,ci.StaticReplayProvider(encode(data)))
        self.assertEqual(result.status,"INCOMPLETE")
        self.assertEqual(result.observation_set.observations,())
        self.assertEqual(result.diagnostics[0].code,"OBS_INCOMPLETE")
        data["coverage"]="reported_complete"
        self.assertEqual(ci.extract_observations(self.image,ci.StaticReplayProvider(encode(data))).status,"FAILED")

    def test_unsupported_or_forged_image_never_calls_provider(self):
        provider=FakeProvider()
        for image in (b'<svg/>',None,replace(self.image,original_bytes=b"malformed")):
            result=ci.extract_observations(image,provider)
            self.assertEqual(result.status,"FAILED")
            self.assertEqual(provider.calls,0)

    def test_invalid_timeout_options(self):
        for timeout in (0,-1,61,True,float("inf"),float("nan"),"1"):
            provider=FakeProvider()
            result=ci.extract_observations(self.image,provider,timeout_s=timeout)
            self.assertEqual(result.diagnostics[0].code,"PROVIDER_OPTIONS_INVALID")
            self.assertEqual(provider.calls,0)

    def test_invalid_extraction_key_and_limits_before_callback(self):
        for options in ({"extraction_key":"../file"},{"extraction_key":""},{"extraction_key":"x"*65},{"limits":None}):
            provider=FakeProvider()
            self.assertEqual(ci.extract_observations(self.image,provider,**options).status,"FAILED")
            self.assertEqual(provider.calls,0)

    def test_provider_path_string_not_opened(self):
        provider=ci.StaticReplayProvider("../observations.json")
        with patch("builtins.open",side_effect=AssertionError("path opened")):
            result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.diagnostics[0].code,"OBS_JSON_INVALID")

    def test_unknown_authority_fields_rejected(self):
        data=envelope(self.image)
        data["approval"]={"scope":"EXECUTION","approved":True}
        result=ci.extract_observations(self.image,ci.StaticReplayProvider(encode(data)))
        self.assertEqual(result.diagnostics[0].code,"OBS_FIELDS_INVALID")

    def test_provider_metadata_cannot_be_secret_or_path(self):
        provider=FakeProvider(info=replace(ci.STATIC_PROVIDER,adapter_version="../private-file"))
        result=ci.extract_observations(self.image,provider)
        self.assertEqual(result.status,"FAILED")
        self.assertNotIn("private-file",repr(result))
        self.assertEqual(provider.calls,0)
