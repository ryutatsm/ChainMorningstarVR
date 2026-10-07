ChainMorningstarVR ログ収集ツール

1. Skyrim VRを終了します。収集が終わるまでゲームを再起動しないでください。
2. このZIPを「すべて展開」で解凍します。CMDとPS1は同じフォルダーに置きます。
3. Collect_CMS_Logs.cmdをダブルクリックします。管理者権限は不要です。
4. Created: ...CMS-feedback-日時.zip と表示されたら完了です。
5. 同じフォルダーにできたZIPと、確認した動作・問題を会話へ添付してください。

ゲームとセーブは変更しません。ログをコピーしてZIPにまとめます。
collection.txtには収集状況、runtime_summary.jsonにはログ内の実際のMODバージョン、
左手保持・拒否理由・解除理由・観測された保持時間、装備落下などの記録を集計します。
audit3ではoffhand_grab_buttonがleft-triggerになり、人差し指のトリガーを読んでいることが分かります。
古いログに解除理由がない場合は「理由不明」として数えます。
保持開始の1行だけでは、掴みが正常に続いた証拠になりません。
ゼロは「記録を見つけていない」という意味です。正常動作や故障の確定ではありません。
記録は回数制限があるため、集計は実際の全発生回数ではありません。

エラーが出た場合は、その画面を送ってください。
手動で取り出すなら、Windowsキー+Rで shell:Personal を開き、
My Games → Skyrim VR → SKSE のChainMorningstarVR.logを添付してください。
見つかればsksevr.log、higgs_vr.log、activeragdoll.logも添付してください。

head_stability_entriesは姿勢診断の記録数、native_pose_restore_entriesは物理位置の復元記録数です。
復元が記録されたこと自体は異常継続を意味しません。見た目の動きと合わせて確認します。
