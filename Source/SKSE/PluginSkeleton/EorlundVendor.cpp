#include "EorlundVendor.hpp"

#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>

#include <cmath>

namespace cms::skyrimvr {
namespace {

constexpr RE::FormID kChainMorningstarLocalFormID = 0x00000800;
constexpr RE::FormID kEorlundMerchantChestLocalFormID = 0x0010FDE6;
constexpr RE::FormID kVendorItemWeaponLocalFormID = 0x0008F958;
constexpr std::string_view kPluginName = "ChainMorningstarVR.esp";
constexpr std::string_view kSkyrimMaster = "Skyrim.esm";

} // namespace

bool EnsureEorlundSellsChainMorningstar()
{
    auto* data = RE::TESDataHandler::GetSingleton();
    if (!data) {
        SKSE::log::error("ChainMorningstarVR: Eorlund vendor injection failed: TESDataHandler unavailable");
        return false;
    }

    auto* weapon = data->LookupForm<RE::TESObjectWEAP>(kChainMorningstarLocalFormID, kPluginName);
    if (!weapon) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection failed: {} local FormID {:06X} not found",
            kPluginName,
            kChainMorningstarLocalFormID);
        return false;
    }

    if (!weapon->IsOneHandedMace()) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection refused: CMS weapon is not One-Hand Mace");
        return false;
    }
    if (weapon->attackDamage != 44 || weapon->value != 550 || std::fabs(weapon->weight - 17.0f) > 0.001f) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection refused: CMS stats mismatch (damage={} weight={:.3f} value={})",
            weapon->attackDamage,
            weapon->weight,
            weapon->value);
        return false;
    }

    auto* vendorKeyword = data->LookupForm<RE::BGSKeyword>(kVendorItemWeaponLocalFormID, kSkyrimMaster);
    if (!vendorKeyword || !weapon->HasKeyword(vendorKeyword)) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection refused: CMS weapon lacks Skyrim.esm VendorItemWeapon [{:08X}]",
            kVendorItemWeaponLocalFormID);
        return false;
    }

    auto* chest = data->LookupForm<RE::TESObjectCONT>(kEorlundMerchantChestLocalFormID, kSkyrimMaster);
    if (!chest) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection failed: MerchantWhiterunEorlundChest [{:08X}] not found",
            kEorlundMerchantChestLocalFormID);
        return false;
    }

    if (!chest->data.flags.any(RE::CONT_DATA::Flag::kRespawn)) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection refused: merchant chest no longer has Respawns flag");
        return false;
    }

    const auto before = chest->CountObjectsInContainer(weapon);
    if (before > 0) {
        SKSE::log::info(
            "ChainMorningstarVR: Eorlund vendor already contains CMS weapon (base count={}); no duplicate added",
            before);
        return true;
    }

    if (!chest->AddObjectToContainer(weapon, 1, nullptr)) {
        SKSE::log::error("ChainMorningstarVR: Eorlund vendor injection failed: AddObjectToContainer returned false");
        return false;
    }

    const auto after = chest->CountObjectsInContainer(weapon);
    if (after != 1) {
        SKSE::log::error(
            "ChainMorningstarVR: Eorlund vendor injection verification failed: expected base count 1, got {}",
            after);
        return false;
    }

    SKSE::log::info(
        "ChainMorningstarVR: Eorlund vendor injection PASS: MerchantWhiterunEorlundChest + CMS_ChainMorningstar x1");
    return true;
}

} // namespace cms::skyrimvr
