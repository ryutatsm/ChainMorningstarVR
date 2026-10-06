#pragma once
#include <cstdint>

namespace cms {
// HIGGS 93bf67b Hand::FindCloseObject/FindOtherWeapon temporarily use exactly
// 0x2C (CustomPick2) for their selection sphere. Physical bodies do not use it.
// The owning adapter opens this scope only around HIGGS Update on its thread,
// after certifying the active right-hand CMS body and an empty left hand.
class OffhandSelectionScope {
public:
    bool begin(std::uint32_t bodyFilter) {
        end();
        if((bodyFilter&0x7f)!=56 || (bodyFilter>>16)==0 || !(bodyFilter&0x8000))
            return false;
        bodyFilter_=bodyFilter&~collisionDisabled;
        return true;
    }
    bool ignore(std::uint32_t a,std::uint32_t b) {
        if(!bodyFilter_)return false;
        const bool match=(a==pickFilter&&(b&~collisionDisabled)==bodyFilter_)||
                         (b==pickFilter&&(a&~collisionDisabled)==bodyFilter_);
        if(match)++rejected_;
        return match;
    }
    std::uint64_t end() {
        const auto count=rejected_;
        bodyFilter_=0;rejected_=0;
        return count;
    }
private:
    static constexpr std::uint32_t pickFilter=0x2C,collisionDisabled=1u<<14;
    std::uint32_t bodyFilter_{};
    std::uint64_t rejected_{};
};
} // namespace cms
