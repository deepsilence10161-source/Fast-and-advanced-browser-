# Swiftra: पढ़कर सुनाना (PLAN 9), on-device (योजना, 19-10-2026)

## Upstream की स्थिति (code प्रमाण, tag 155.0.8059.80)

| हिस्सा | फ़ाइल | नतीजा |
|---|---|---|
| Readability जाँच + text | `chrome/browser/readaloud/read_aloud_service.cc` | `dom_distiller::url_utils::IsUrlDistillable()` और DOM Distiller viewer से page text लेता है। यह upstream है और काम आएगा |
| आवाज़ बनाना | `chrome/browser/readaloud/audio_generation/speech_synthesis_broker.cc` | `ExecuteModel(ModelBasedCapabilityKey::kReadAloudSynthesize)`, यानी Google का server-side model execution (account/API key चाहिए) |
| Server synthesizer flag | `chrome/browser/readaloud/android/read_aloud_features.cc` | `IsReadAloudServerSynthesizerEnabled()`, metrics client ID और server experiment भी भेजता है |

नतीजा: Chrome का "Listen to this page" Google server पर निर्भर है। Swiftra में यह उपलब्ध नहीं (static)।

## Swiftra का रास्ता (Chrome से अलग: offline, कोई data बाहर नहीं)

1. Menu में "पढ़कर सुनाएँ" item, केवल तब दिखे जब `IsUrlDistillable(url)` true हो।
2. Text: upstream DOM Distiller (वही जो "Simplified view" में है)। कोई network request नहीं।
3. आवाज़: Android `android.speech.tts.TextToSpeech` (फ़ोन का on-device engine), वाक्य-दर-वाक्य `speak(QUEUE_ADD)`; play/pause/गति के controls; tab बदलने पर रुक जाए।
4. Privacy: कोई metrics ID नहीं, server नहीं। Engine user के फ़ोन वाला ही रहेगा।
5. E2E: example.org (distillable नहीं, इसलिए item नहीं दिखना चाहिए) + loopback article page (item दिखे, `TextToSpeech` utterance callbacks आएँ)। Emulator का Pico/Google TTS engine उपलब्ध हो तभी PASS, वरना NOT RUN।

जोखिम: `TextToSpeech` engine हर फ़ोन पर अलग है; भारतीय भाषाओं की आवाज़ engine पर निर्भर है।
