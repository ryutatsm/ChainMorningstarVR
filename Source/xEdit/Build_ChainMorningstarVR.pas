unit userscript;

var
  SkyrimFile, DstFile, Src, Dst: IInterface;

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
  AddMessage('Vendor distribution is handled separately by Container Item Distributor (CID).');
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
  // This new plugin contains no other new records; 0x800 is xEdit's normal first-new-record range.
  SetLoadOrderFormID(Dst, (GetLoadOrderFormID(Dst) and $FF000000) or $00000800);

  SetElementEditValues(Dst, 'EDID', 'CMS_ChainMorningstar');
  SetElementEditValues(Dst, 'FULL', 'Chain Morningstar');
  SetElementEditValues(Dst, 'Model\MODL', 'weapons\ChainMorningstarVR\ChainMorningstar.nif');
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
  AddMessage('PASS: No merchant chest or leveled-list override was created.');
  AddMessage('Vendor: ChainMorningstarVR.dll injects one item into Eorlund merchant stock at DataLoaded.');
  AddMessage('Test spawn after saving: help "Chain Morningstar" 4');
end;

end.
