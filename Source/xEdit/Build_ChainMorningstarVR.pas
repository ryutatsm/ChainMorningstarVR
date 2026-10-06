unit userscript;

var
  SkyrimFile, DstFile, Src, Dst, FirstPersonSrc, FirstPersonDst, VendorChest: IInterface;

procedure SetCMSBounds(Rec: IInterface);
var
  Bounds, MinBounds, MaxBounds: IInterface;
begin
  // Outward-rounded bounds of the current reference mesh in Skyrim units.
  // Older xEdit used six flat fields; current definitions use Min/Max vectors.
  Bounds := ElementBySignature(Rec, 'OBND');
  if ElementCount(Bounds) = 6 then begin
    SetNativeValue(ElementByIndex(Bounds, 0), -16);
    SetNativeValue(ElementByIndex(Bounds, 1), -21);
    SetNativeValue(ElementByIndex(Bounds, 2), -12);
    SetNativeValue(ElementByIndex(Bounds, 3), 16);
    SetNativeValue(ElementByIndex(Bounds, 4), 119);
    SetNativeValue(ElementByIndex(Bounds, 5), 12);
  end else begin
    MinBounds := ElementByIndex(Bounds, 0);
    MaxBounds := ElementByIndex(Bounds, 1);
    SetNativeValue(ElementByIndex(MinBounds, 0), -16);
    SetNativeValue(ElementByIndex(MinBounds, 1), -21);
    SetNativeValue(ElementByIndex(MinBounds, 2), -12);
    SetNativeValue(ElementByIndex(MaxBounds, 0), 16);
    SetNativeValue(ElementByIndex(MaxBounds, 1), 119);
    SetNativeValue(ElementByIndex(MaxBounds, 2), 12);
  end;
end;

function Initialize: integer;
begin
  Result := 0;

  if LowerCase(wbAppName) <> 'tes5vr' then begin
    AddMessage('ERROR: This script must run in Skyrim VR mode (TES5VREdit / -TES5VR). Current mode: ' + wbAppName);
    Result := 1;
    Exit;
  end;

  AddMessage('ChainMorningstarVR: clean-build WEAP generator');
  AddMessage('Source template: Skyrim.esm Steel Mace [WEAP:00013988].');
  AddMessage('Vendor distribution is injected in memory by ChainMorningstarVR.dll at DataLoaded.');
  AddMessage('No vanilla merchant/container/leveled-list record is overridden.');

  SkyrimFile := FileByName('Skyrim.esm');
  if not Assigned(SkyrimFile) then begin
    AddMessage('ERROR: Skyrim.esm is not loaded.');
    Result := 1;
    Exit;
  end;

  Src := RecordByFormID(SkyrimFile, $00013988, False);
  if not Assigned(Src) then begin
    AddMessage('ERROR: Skyrim.esm Steel Mace [00013988] was not found.');
    Result := 1;
    Exit;
  end;

  if Signature(Src) <> 'WEAP' then begin
    AddMessage('ERROR: [00013988] is not a WEAP record in the loaded Skyrim.esm.');
    Result := 1;
    Exit;
  end;

  if GetElementEditValues(Src, 'EDID') <> 'SteelMace' then begin
    AddMessage('ERROR: [00013988] EDID is not SteelMace. Refusing unexpected master record.');
    Result := 1;
    Exit;
  end;

  FirstPersonSrc := LinksTo(ElementBySignature(Src, 'WNAM'));
  if not Assigned(FirstPersonSrc) then begin
    AddMessage('ERROR: SteelMace first-person model reference is missing.');
    Result := 1;
    Exit;
  end;
  if Signature(FirstPersonSrc) <> 'STAT' then begin
    AddMessage('ERROR: SteelMace first-person model is not a STAT record.');
    Result := 1;
    Exit;
  end;
  VendorChest := RecordByFormID(SkyrimFile, $0010FDE6, False);
  if not Assigned(VendorChest) then begin
    AddMessage('ERROR: Target vendor container is missing.');
    Result := 1;
    Exit;
  end;
  if Signature(VendorChest) <> 'CONT' then begin
    AddMessage('ERROR: Target vendor FormID is not a container.');
    Result := 1;
    Exit;
  end;
  if GetElementEditValues(VendorChest, 'EDID') <> 'MerchantWhiterunEorlundChest' then begin
    AddMessage('ERROR: Target vendor container editor ID mismatch.');
    Result := 1;
    Exit;
  end;
  if (GetElementNativeValues(VendorChest, 'DATA\Flags') and 2) = 0 then begin
    AddMessage('ERROR: Target vendor container does not respawn.');
    Result := 1;
    Exit;
  end;

  DstFile := AddNewFileName('ChainMorningstarVR.esp');
  if not Assigned(DstFile) then begin
    AddMessage('ERROR: Could not create ChainMorningstarVR.esp. Remove/rename existing file and retry.');
    Result := 1;
    Exit;
  end;

  AddRequiredElementMasters(Src, DstFile, False);

  // asNew=True: creates a new FormID instead of overriding vanilla Steel Mace.
  // deepCopy=True: preserves one-handed mace keywords/equip/sound/impact structure.
  Dst := wbCopyElementToFile(Src, DstFile, True, True);
  if not Assigned(Dst) then begin
    AddMessage('ERROR: Could not create the new WEAP record.');
    Result := 1;
    Exit;
  end;

  // The SKSE runtime resolves this record by plugin-local FormID, so keep it deterministic.
  // 0x800 is the weapon ABI. The new first-person STAT uses 0x801.
  SetLoadOrderFormID(Dst, (GetLoadOrderFormID(Dst) and $FF000000) or $00000800);

  AddRequiredElementMasters(FirstPersonSrc, DstFile, False);
  FirstPersonDst := wbCopyElementToFile(FirstPersonSrc, DstFile, True, True);
  if not Assigned(FirstPersonDst) then begin
    AddMessage('ERROR: Could not create the new first-person STAT. Do not save this incomplete plugin.');
    Result := 1;
    Exit;
  end;
  SetLoadOrderFormID(FirstPersonDst, (GetLoadOrderFormID(FirstPersonDst) and $FF000000) or $00000801);
  SetElementEditValues(FirstPersonDst, 'EDID', 'CMS_ChainMorningstarFirstPerson');
  SetElementEditValues(FirstPersonDst, 'Model\MODL', 'weapons\ChainMorningstarVR\ChainMorningstar.nif');

  SetElementEditValues(Dst, 'EDID', 'CMS_ChainMorningstar');
  SetElementEditValues(Dst, 'FULL', 'チェーンドモーニングスター');
  SetElementEditValues(Dst, 'Model\MODL', 'weapons\ChainMorningstarVR\ChainMorningstar.nif');
  SetElementEditValues(Dst, 'WNAM', IntToHex(GetLoadOrderFormID(FirstPersonDst), 8));
  SetCMSBounds(Dst);
  SetCMSBounds(FirstPersonDst);
  // Source texture hashes/alternate textures belong to SteelMace's NIF.
  if ElementExists(Dst, 'Model\MODT') then RemoveElement(Dst, 'Model\MODT');
  if ElementExists(Dst, 'Model\MODS') then RemoveElement(Dst, 'Model\MODS');
  if ElementExists(FirstPersonDst, 'Model\MODT') then RemoveElement(FirstPersonDst, 'Model\MODT');
  if ElementExists(FirstPersonDst, 'Model\MODS') then RemoveElement(FirstPersonDst, 'Model\MODS');
  // Use native numeric values so Windows locale/decimal separators cannot affect the result.
  SetElementNativeValues(Dst, 'DATA\Value', 550);
  SetElementNativeValues(Dst, 'DATA\Weight', 17.0);
  SetElementNativeValues(Dst, 'DATA\Damage', 44);

  CleanMasters(DstFile);

  AddMessage('PASS: ChainMorningstarVR.esp created.');
  AddMessage('PASS: EDID CMS_ChainMorningstar / local FormID 00000800');
  AddMessage('PASS: one-handed mace template = Skyrim.esm SteelMace [00013988]');
  AddMessage('PASS: Damage 44 / Weight 17 / Value 550');
  AddMessage('PASS: Model weapons\ChainMorningstarVR\ChainMorningstar.nif');
  AddMessage('PASS: WNAM links to new CMS_ChainMorningstarFirstPerson [00000801], not SteelMace.');
  AddMessage('PASS: No merchant chest or leveled-list override was created.');
  AddMessage('Vendor: ChainMorningstarVR.dll injects one item into Eorlund merchant stock at DataLoaded.');
  AddMessage('Test spawn after saving: help "CMS_ChainMorningstar" 4');
end;

end.
