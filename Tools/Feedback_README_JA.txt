ChainMorningstarVR ログ収集ツール audit5

1. Skyrim VRを終了します。収集が終わるまでゲームを再起動しないでください。
2. このZIPを展開し、Collect_CMS_Logs.cmdをダブルクリックします。管理者権限は不要です。
3. 今回はCMD単体で実行できます。別添PS1は同じ処理の読めるソースです。
4. 原則としてデスクトップのCMS-feedbackフォルダーにCMS-feedback-日時.zipを作ります。
5. 作成したZIPの場所が自動で開きます。そのZIPと確認結果を添付してください。

デスクトップへ書けない場合は、別の書き込み可能な場所に保存して画面にパスを表示します。
一部のログがロックされていても、読めたログとエラー記録でZIPを作ります。
圧縮が失敗した場合はZIP_ERROR.txtとコピー済みのログを残します。
それでも生成されない場合は、止まった画面のスクリーンショットを送ってください。

ゲームやセーブを変更せず、ログをコピーします。32MiBを超えるログは末尾32MiBを収集します。
collection.txtに欠落・読み取り失敗・切り詰めを記録します。
runtime_summary.jsonには実際のMODバージョン、保持、装備落下、追加音の再生要求を集計します。
記録がゼロでも故障とは断定できません。音の再生要求が受理されても、実際の聞こえ方は別途確認が必要です。

手動で取り出すなら、Windowsキー+Rで shell:Personal を開き、
My Games → Skyrim VR → SKSE のChainMorningstarVR.logを添付してください。
見つかればsksevr.log、higgs_vr.log、activeragdoll.logも添付してください。
