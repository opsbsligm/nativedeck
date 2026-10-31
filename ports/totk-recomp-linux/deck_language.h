#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static inline uint64_t deck_desired_language() {
    const char *language = std::getenv("TOTK_LANG");
    if (!language || !*language) language = "zh-Hans";
    static const char *const supported[] = {
        "ja", "en-US", "en-GB", "fr", "fr-CA", "de", "it", "es", "es-419",
        "ko", "nl", "pt", "pt-BR", "ru", "zh-CN", "zh-TW", "zh-Hans", "zh-Hant"
    };
    bool valid = false;
    for (const char *code : supported) {
        if (std::strcmp(language, code) == 0) { valid = true; break; }
    }
    if (!valid) {
        std::fprintf(stderr, "[oe] unsupported TOTK_LANG; using zh-Hans\n");
        language = "zh-Hans";
    }
    uint64_t packed = 0;
    std::memcpy(&packed, language, std::strlen(language));
    return packed;
}
