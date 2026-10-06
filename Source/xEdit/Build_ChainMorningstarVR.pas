unit userscript;

var
  SkyrimFile, DstFile, Src, Dst: IInterface;
  EorlundChest, EorlundChestOverride, Items, ItemEntry: IInterface;

function Initialize: integer;
begin
  Result := 0;

  AddMessage('ChainMorningstarVR: clean-build WEAP + Eorlund vendor generator');
  AddMessage('Source template: Skyrim.esm Steel Mace [WEAP:00013988].');
  AddMessage('Vendor target: MerchantWhiterunEorlundChest [CONT:0010FDE6].');
  AddMessage('No record from any previous Chain Morningstar mod is used.');

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

  EorlundChest := RecordByFormID(SkyrimFile, $0010FDE6, False);
  if not Assigned(EorlundChest) then begin
    AddMessage('ERROR: Eorlund merchant chest [0010FDE6] was not found.');
    Result := 1;
    Exit;
  end;

  if Signature(EorlundChest) <> 'CONT' then begin
    AddMessage('ERROR: [0010FDE6] is not a CONT record. Refusing to patch vendor.');
    Result := 1;
    Exit;
  end;

  if GetElementEditValues(EorlundChest, 'EDID') <> 'MerchantWhiterunEorlundChest' then begin
    AddMessage('ERROR: [0010FDE6] EDID mismatch. Refusing to patch an unexpected container.');
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
  AddRequiredElementMasters(EorlundChest, DstFile, False);

  Dst := wbCopyElementToFile(Src, DstFile, True, True);
  if not Assigned(Dst) then begin
    AddMessage('ERROR: Could not create the new WEAP record.');
    Result := 1;
    Exit;
  end;

  SetElementEditValues(Dst, 'EDID', 'CMS_ChainMorningstar');
  SetElementEditValues(Dst, 'FULL', 'Chain Morningstar');
  SetElementEditValues(Dst, 'Model\MODL', 'weapons\ChainMorningstarVR\ChainMorningstar.nif');
  SetElementEditValues(Dst, 'DATA\Value', '550');
  SetElementEditValues(Dst, 'DATA\Weight', '17.000000');
  SetElementEditValues(Dst, 'DATA\Damage', '44');

  EorlundChestOverride := wbCopyElementToFile(EorlundChest, DstFile, False, True);
  if not Assigned(EorlundChestOverride) then begin
    AddMessage('ERROR: Could not create Eorlund merchant chest override.');
    Result := 1;
    Exit;
  end;

  Items := ElementByPath(EorlundChestOverride, 'Items');
  if not Assigned(Items) then
    Items := Add(EorlundChestOverride, 'Items', True);
  if not Assigned(Items) then begin
    AddMessage('ERROR: Could not access/create merchant chest Items array.');
    Result := 1;
    Exit;
  end;

  ItemEntry := ElementAssign(Items, HighInteger, nil, False);
  if not Assigned(ItemEntry) then begin
    AddMessage('ERROR: Could not append weapon to Eorlund merchant chest.');
    Result := 1;
    Exit;
  end;

  SetElementEditValues(ItemEntry, 'CNTO\Item', Name(Dst));
  SetElementEditValues(ItemEntry, 'CNTO\Count', '1');

  CleanMasters(DstFile);

  AddMessage('PASS: ChainMorningstarVR.esp created.');
  AddMessage('PASS: EDID CMS_ChainMorningstar');
  AddMessage('PASS: one-handed mace template = Skyrim.esm SteelMace [00013988]');
  AddMessage('PASS: Damage 44 / Weight 17 / Value 550');
  AddMessage('PASS: Model weapons\ChainMorningstarVR\ChainMorningstar.nif');
  AddMessage('PASS: Added to MerchantWhiterunEorlundChest [0010FDE6], count 1');
  AddMessage('VALIDATION: reopen ChainMorningstarVR.esp in SSEEdit and Check for Errors.');
  AddMessage('VALIDATION: in game, help "Chain Morningstar" 4 can confirm the WEAP record.');
end;

end.
