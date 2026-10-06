unit userscript;

var
  ModFile, G, Rec, WeaponRec: IInterface;
  i: integer;

procedure Fail(const S: string);
begin
  AddMessage('ERROR: ' + S);
end;

function Initialize: integer;
begin
  Result := 1;
  WeaponRec := nil;

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

  if GetElementEditValues(WeaponRec, 'FULL') <> 'Chain Morningstar' then begin
    Fail('FULL name mismatch.');
    Exit;
  end;
  if GetElementEditValues(WeaponRec, 'DATA\Damage') <> '44' then begin
    Fail('Damage is not 44.');
    Exit;
  end;
  if Abs(StrToFloat(GetElementEditValues(WeaponRec, 'DATA\Weight')) - 17.0) > 0.001 then begin
    Fail('Weight is not 17.');
    Exit;
  end;
  if GetElementEditValues(WeaponRec, 'DATA\Value') <> '550' then begin
    Fail('Value is not 550.');
    Exit;
  end;
  if LowerCase(GetElementEditValues(WeaponRec, 'Model\MODL')) <>
     'weapons\chainmorningstarvr\chainmorningstar.nif' then begin
    Fail('Model path mismatch.');
    Exit;
  end;

  // The ESP must contain no merchant chest or leveled-list override.
  G := GroupBySignature(ModFile, 'CONT');
  if Assigned(G) and (ElementCount(G) > 0) then begin
    Fail('Unexpected CONT override found. Vendor distribution must be CID-only.');
    Exit;
  end;

  G := GroupBySignature(ModFile, 'LVLI');
  if Assigned(G) and (ElementCount(G) > 0) then begin
    Fail('Unexpected LVLI override found. Vendor distribution must be CID-only.');
    Exit;
  end;

  AddMessage('PASS: ChainMorningstarVR.esp structural validation succeeded.');
  AddMessage('PASS: WEAP CMS_ChainMorningstar / Damage 44 / Weight 17 / Value 550.');
  AddMessage('PASS: Model path weapons\ChainMorningstarVR\ChainMorningstar.nif.');
  AddMessage('PASS: No CONT or LVLI overrides are present.');
  AddMessage('NEXT: run xEdit Check for Errors on ChainMorningstarVR.esp.');
  Result := 0;
end;

end.
