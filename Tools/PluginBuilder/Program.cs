using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
using Mutagen.Bethesda.Skyrim.Assets;
using Noggog;

const string Edid = "CMS_ChainMorningstar";
const string DisplayName = "Chain Morningstar";
const string ModelPath = @"weapons\ChainMorningstarVR\ChainMorningstar.nif";

var outputPath = args.Length > 0 ? args[0] : "ChainMorningstarVR.esp";
Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);

var modKey = ModKey.FromNameAndExtension(Path.GetFileName(outputPath));
var mod = new SkyrimMod(modKey, SkyrimRelease.SkyrimSE);

// This plugin is generated from project-owned constants only. It does not copy
// records from any previous Chain Morningstar project or require Skyrim.esm bytes
// during CI. References below point at stable vanilla master records by FormID.
var weapon = mod.Weapons.AddNew();
weapon.EditorID = Edid;
weapon.Name = DisplayName;
weapon.Model = new Model
{
    File = new AssetLink<SkyrimModelAssetType>(ModelPath)
};

// EitherHand [EQUP:00013F44].
weapon.EquipmentType.SetTo(FormKey.Factory("013F44:Skyrim.esm"));

// Vanilla Skyrim 1H blunt/mace sound and impact contracts.
weapon.PickUpSound.SetTo(FormKey.Factory("03C7BE:Skyrim.esm"));          // ITMGenericWeaponUpSD
weapon.PutDownSound.SetTo(FormKey.Factory("03C7C0:Skyrim.esm"));        // ITMGenericWeaponDownSD
weapon.AttackSound.SetTo(FormKey.Factory("105D43:Skyrim.esm"));         // WPNSwingBlunt1Hand
weapon.EquipSound.SetTo(FormKey.Factory("03DE2A:Skyrim.esm"));          // WPNMace1HandDrawSD
weapon.UnequipSound.SetTo(FormKey.Factory("03DE2B:Skyrim.esm"));        // WPNMace1HandSheatheSD
weapon.ImpactDataSet.SetTo(FormKey.Factory("0193B7:Skyrim.esm"));       // WPNzBluntImpactSet
weapon.BlockBashImpact.SetTo(FormKey.Factory("0193C7:Skyrim.esm"));     // WPNBashBluntImpactSet
weapon.AlternateBlockMaterial.SetTo(FormKey.Factory("0774C1:Skyrim.esm")); // MaterialBlockBlunt

weapon.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>>
{
    FormKey.Factory("01E714:Skyrim.esm"), // WeapTypeMace
    FormKey.Factory("01E719:Skyrim.esm"), // WeapMaterialSteel
    FormKey.Factory("08F958:Skyrim.esm")  // VendorItemWeapon
};

weapon.BasicStats = new WeaponBasicStats
{
    Value = 550,
    Weight = 17.0f,
    Damage = 44
};

weapon.Data = new WeaponData
{
    AnimationType = WeaponAnimationType.OneHandMace,
    Speed = 0.8f,
    Reach = 1.0f,
    Flags = 0,
    AttackAnimation = WeaponData.AttackAnimationType.Default,
    NumProjectiles = 0,
    RangeMin = 0.0f,
    RangeMax = 0.0f,
    OnHit = WeaponData.OnHitType.NoDismemberOrExplode,
    AnimationAttackMult = 1.0f,
    Skill = Skill.OneHanded,
    Resist = ActorValue.None,
    Stagger = 1.0f
};

await mod.BeginWrite
    .ToPath(outputPath)
    .WithNoLoadOrder()
    .WithMastersListContent(Mutagen.Bethesda.Plugins.Binary.Parameters.MastersListContentOption.Iterate)
    .SingleThread()
    .WriteAsync();

// Release gate: re-open the exact bytes written and validate the fields that
// define gameplay identity. This catches serializer/API mistakes in CI.
using var check = SkyrimMod.CreateFromBinaryOverlay(outputPath, SkyrimRelease.SkyrimSE);
var records = check.Weapons.Where(x => x.EditorID == Edid).ToList();
if (records.Count != 1)
    throw new InvalidOperationException($"Expected exactly one {Edid} WEAP record, got {records.Count}.");

var got = records[0];
if (got.Name?.String != DisplayName)
    throw new InvalidOperationException($"FULL mismatch: {got.Name?.String}");
if (got.BasicStats is null ||
    got.BasicStats.Damage != 44 ||
    Math.Abs(got.BasicStats.Weight - 17.0f) > 0.0001f ||
    got.BasicStats.Value != 550)
    throw new InvalidOperationException("DATA mismatch: expected Damage 44 / Weight 17 / Value 550.");
if (got.Data is null || got.Data.AnimationType != WeaponAnimationType.OneHandMace)
    throw new InvalidOperationException("DNAM mismatch: weapon is not OneHandMace.");
if (got.Data.Skill != Skill.OneHanded)
    throw new InvalidOperationException("DNAM mismatch: skill is not OneHanded.");
if (got.Model?.File.GivenPath != ModelPath)
    throw new InvalidOperationException($"Model mismatch: {got.Model?.File.GivenPath}");
if (got.EquipmentType.FormKey != FormKey.Factory("013F44:Skyrim.esm"))
    throw new InvalidOperationException("Equipment type is not EitherHand.");

var vanillaLinks = new (string Name, FormKey Got, FormKey Want)[]
{
    ("PickUpSound", got.PickUpSound.FormKey, FormKey.Factory("03C7BE:Skyrim.esm")),
    ("PutDownSound", got.PutDownSound.FormKey, FormKey.Factory("03C7C0:Skyrim.esm")),
    ("AttackSound", got.AttackSound.FormKey, FormKey.Factory("105D43:Skyrim.esm")),
    ("EquipSound", got.EquipSound.FormKey, FormKey.Factory("03DE2A:Skyrim.esm")),
    ("UnequipSound", got.UnequipSound.FormKey, FormKey.Factory("03DE2B:Skyrim.esm")),
    ("ImpactDataSet", got.ImpactDataSet.FormKey, FormKey.Factory("0193B7:Skyrim.esm")),
    ("BlockBashImpact", got.BlockBashImpact.FormKey, FormKey.Factory("0193C7:Skyrim.esm")),
    ("AlternateBlockMaterial", got.AlternateBlockMaterial.FormKey, FormKey.Factory("0774C1:Skyrim.esm")),
};
foreach (var link in vanillaLinks)
{
    if (link.Got != link.Want)
        throw new InvalidOperationException($"{link.Name} mismatch: {link.Got} != {link.Want}");
}

var keywordKeys = got.Keywords?.Select(x => x.FormKey).ToHashSet() ?? [];
foreach (var required in new[]
{
    FormKey.Factory("01E714:Skyrim.esm"),
    FormKey.Factory("01E719:Skyrim.esm"),
    FormKey.Factory("08F958:Skyrim.esm")
})
{
    if (!keywordKeys.Contains(required))
        throw new InvalidOperationException($"Missing required keyword {required}.");
}

Console.WriteLine("CMS_ESP_VALIDATE: PASS");
Console.WriteLine($"CMS_ESP_FORMKEY: {got.FormKey}");
Console.WriteLine("CMS_ESP_STATS: damage=44 weight=17 value=550");
Console.WriteLine("CMS_ESP_TYPE: OneHandMace / OneHanded / EitherHand");
Console.WriteLine("CMS_ESP_VANILLA_AUDIO_IMPACT_LINKS: PASS");
Console.WriteLine($"CMS_ESP_MODEL: {got.Model!.File.GivenPath}");
