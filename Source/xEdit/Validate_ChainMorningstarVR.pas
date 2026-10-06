unit userscript;

var
  ModFile, G, Rec, WeaponRec, FirstPersonRec, KWDA, KW: IInterface;
  i, j: integer;
  HasVendorItemWeapon: boolean;

procedure Fail(const S: string);
begin
  AddMessage('ERROR: ' + S);
end;

function Initialize: integer;
begin
  Result := 1;

  if LowerCase(wbAppName) <> 'tes5vr' then begin
    AddMessage('ERROR: This script must run in Skyrim VR mode (TES5VREdit / -TES5VR). Current mode: ' + wbAppName);
    Result := 1;
    Exit;
  end;
  WeaponRec := nil;
  HasVendorItemWeapon := False;

  ModFile := FileByName('ChainMorningstarVR.esp');
  if not Assigned(ModFile) then begin
    Fail('ChainMorningstarVR.esp is not loaded.');
    Exit;
  end;

  G := GroupBySignature(ModFile, 'WEAP');
  if Assigned(G) then
    for i := 0 to ElementCount(G) - 1 do begin
      Rec := ElementByIndex(G, i);
      if GetElementEditValues(Rec, 'EDID') = 'CMS_ChainMorningstar' then begin
        WeaponRec := Rec;
        Break;
      end;
    end;

  if not Assigned(WeaponRec) then begin
    Fail('CMS_ChainMorningstar WEAP record not found.');
    Exit;
  end;

  if (GetLoadOrderFormID(WeaponRec) and $00FFFFFF) <> $00000800 then begin
    Fail('Local FormID is not 00000800.');
    Exit;
  end;

  if GetElementEditValues(WeaponRec, 'FULL') <> 'チェーンドモーニングスター' then begin
    Fail('FULL name mismatch.');
    Exit;
  end;
  if GetElementNativeValues(WeaponRec, 'DATA\Damage') <> 44 then begin
    Fail('Damage is not 44.');
    Exit;
  end;
  if Abs(GetElementNativeValues(WeaponRec, 'DATA\Weight') - 17.0) > 0.001 then begin
    Fail('Weight is not 17.');
    Exit;
  end;
  if GetElementNativeValues(WeaponRec, 'DATA\Value') <> 550 then begin
    Fail('Value is not 550.');
    Exit;
  end;
  if GetElementNativeValues(WeaponRec, 'DNAM\Animation Type') <> 4 then begin
    Fail('Weapon is not classified as One-Hand Mace (Animation Type 4).');
    Exit;
  end;

  KWDA := ElementBySignature(WeaponRec, 'KWDA');
  if Assigned(KWDA) then
    for j := 0 to ElementCount(KWDA) - 1 do begin
      KW := LinksTo(ElementByIndex(KWDA, j));
      if Assigned(KW) then
        if GetElementEditValues(KW, 'EDID') = 'VendorItemWeapon' then begin
          HasVendorItemWeapon := True;
          Break;
        end;
    end;

  if not HasVendorItemWeapon then begin
    Fail('VendorItemWeapon keyword is missing.');
    Exit;
  end;

  if LowerCase(GetElementEditValues(WeaponRec, 'Model\MODL')) <>
     'weapons\chainmorningstarvr\chainmorningstar.nif' then begin
    Fail('Model path mismatch.');
    Exit;
  end;

  FirstPersonRec := LinksTo(ElementBySignature(WeaponRec, 'WNAM'));
  if not Assigned(FirstPersonRec) then begin
    Fail('WNAM first-person model reference is missing.');
    Exit;
  end;
  if Signature(FirstPersonRec) <> 'STAT' then begin
    Fail('WNAM does not reference a STAT record.');
    Exit;
  end;
  if GetFileName(GetFile(FirstPersonRec)) <> GetFileName(ModFile) then begin
    Fail('WNAM still points outside this plugin (possible inherited SteelMace model).');
    Exit;
  end;
  if (GetLoadOrderFormID(FirstPersonRec) and $00FFFFFF) <> $00000801 then begin
    Fail('First-person STAT local FormID is not 00000801.');
    Exit;
  end;
  if GetElementEditValues(FirstPersonRec, 'EDID') <> 'CMS_ChainMorningstarFirstPerson' then begin
    Fail('First-person STAT editor ID mismatch.');
    Exit;
  end;
  if LowerCase(GetElementEditValues(FirstPersonRec, 'Model\MODL')) <>
     'weapons\chainmorningstarvr\chainmorningstar.nif' then begin
    Fail('First-person STAT model path mismatch.');
    Exit;
  end;

  // The ESP must contain no merchant chest or leveled-list override.
  G := GroupBySignature(ModFile, 'CONT');
  if Assigned(G) then
    if ElementCount(G) > 0 then begin
      Fail('Unexpected CONT override found. Vendor distribution must be runtime-only.');
      Exit;
    end;

  G := GroupBySignature(ModFile, 'LVLI');
  if Assigned(G) then
    if ElementCount(G) > 0 then begin
      Fail('Unexpected LVLI override found. Vendor distribution must be runtime-only.');
      Exit;
    end;

  AddMessage('PASS: ChainMorningstarVR.esp structural validation succeeded.');
  AddMessage('PASS: WEAP CMS_ChainMorningstar [local FormID 00000800].');
  AddMessage('PASS: One-Hand Mace / VendorItemWeapon / Damage 44 / Weight 17 / Value 550.');
  AddMessage('PASS: Model path weapons\ChainMorningstarVR\ChainMorningstar.nif.');
  AddMessage('PASS: WNAM uses custom first-person STAT [00000801] with the same NIF.');
  AddMessage('PASS: No CONT or LVLI overrides are present.');
  AddMessage('NEXT: run xEdit Check for Errors on ChainMorningstarVR.esp.');
  Result := 0;
end;

end.
