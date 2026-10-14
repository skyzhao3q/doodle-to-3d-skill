# doodle-to-3d

**日本語** | [English](README.en.md)

子どもの落書き（写真1枚）から、**鉛筆の線とマーカーの塗りを残したまま**3Dキャラクターを作り、空を飛んだり火を吐いたりするアニメーション（効果音付き）まで仕上げるパイプラインです。Claude Code や Codex などのコーディングエージェントが同じ手順を再現できるよう、Skill としてまとめています。

<table>
  <tr>
    <th>子どもが描いたカード</th>
    <th>空を飛ぶ</th>
    <th>「ファイヤー」を吐く</th>
  </tr>
  <tr>
    <td><img src="docs/images/drawing.jpg" width="260" alt="子どもが描いた「むらさきドラゴン」のカード"></td>
    <td><img src="docs/images/swoop.gif" width="230" alt="空を飛ぶむらさきドラゴン"></td>
    <td><img src="docs/images/fire.gif" width="230" alt="青い炎を吐くむらさきドラゴン"></td>
  </tr>
</table>

実際の動画は 1080×1920（縦）、24fps で、風・羽ばたき・炎の効果音が付きます（上の GIF は軽量化したものです）。

## 何ができるの？

写真から動画まで、次の順番で進みます。

| | 手順 | 中身 |
|---|---|---|
| 1 | キャラだけを取り出す | 写真の傾きを直し、Gemini でキャラだけを白背景に描き直す（子どもの線は描き直さない） |
| 2 | パーツに分ける | 頭・体・腕・足・翼・しっぽに分割。隠れていた部分は、同じ絵の塗りをコピーして埋める |
| 3 | 足りない部分を補う | 描かれていない奥の翼や腕は、子どもが描いた反対側を反転して作る |
| 4 | 3D にして動かす | 絵をぬいぐるみのようにふくらませ、Blender で羽ばたき・足こぎ・手振り |
| 5 | 空と炎を描く | Gemini が同じ「子どもの絵」タッチで空と炎を描き、雲もふくらませて流す |
| 6 | 音を付けて書き出す | 風・羽ばたき・吸い込み・炎の音を合成して、動画に合わせて鳴らす |

<table>
  <tr>
    <th>1. 取り出したキャラ</th>
    <th>2〜3. 9つのパーツ（奥の翼と右腕は反転で補った）</th>
  </tr>
  <tr>
    <td><img src="docs/images/cutout.jpg" width="220" alt="Gemini で取り出したキャラ"></td>
    <td><img src="docs/images/parts.jpg" width="560" alt="9つに分けたパーツ"></td>
  </tr>
</table>

### 大事にしていること：子どもの線を消さない

最初は、設定画からきれいな3Dモデルを組み立てる方法も試しました。整ってはいるものの、子どもの線がすべて消えて「色の塊」になってしまいます（下図の右2つ）。

<img src="docs/images/first_3d.jpg" width="600" alt="左が子どもの絵、右2つが最初に作ったきれいな3Dモデル">

そこでこのパイプラインでは、見えている部分はすべて元の絵の画素を使います。補う部分も、子どもが描いた線と塗り（反転・コピー）だけで埋めています。

## シーン

| モード | 長さ | 内容 |
|---|---|---|
| `swoop` | 15秒 | 下から飛び込み、左右に揺れながら上へ抜ける |
| `hover` | 10秒 | その場で羽ばたきながら上昇する |
| `fire` | 11秒 | 息を吸って、口から炎を吐く（炎も子どもの絵タッチ） |

## 必要なもの

- Python 3.10 以上
- [Blender](https://www.blender.org/download/)（`blender` コマンドで起動できること）。**Blender 5.2**（Eevee）で動作確認しています。4.x 系は未確認です。
- [ffmpeg](https://ffmpeg.org/)
- **Gemini API キー**（画像生成）。1枚の絵につき画像生成3回ほどで、執筆時点では1回あたり 0.1〜0.2 ドル程度です。最新の料金は各自で確認してください。
- macOS / Linux / Windows（開発は macOS）

## セットアップ

```bash
git clone https://github.com/skyzhao3q/doodle-to-3d-skill.git
cd doodle-to-3d-skill
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# iPhone の写真（HEIC）を使う場合
pip install pillow-heif
```

### Gemini API キーの設定

1. [Google AI Studio](https://aistudio.google.com/apikey) でキーを発行します。
2. 環境変数で渡します（推奨）。
   ```bash
   export GEMINI_API_KEY="発行したキー"
   ```
   または `.env.example` を `.env` にコピーして書き込みます（リポジトリ直下か、コマンドを実行するディレクトリ）。`.env` は git の管理対象外です。**キーをコミットしたり、チャットや Issue に貼ったりしないでください。**
3. 任意：`GEMINI_IMAGE_MODEL` で画像モデルを変更できます（既定は `gemini-3-pro-image-preview`）。

動作確認：

```bash
python3 -c "import cv2, numpy, scipy, PIL, google.genai; print('python ok')"
blender --version
ffmpeg -version | head -1
python3 -c "import os; print('GEMINI_API_KEY set:', bool(os.environ.get('GEMINI_API_KEY')))"
```

## コーディングエージェントで使う

**Claude Code**：個人用 Skill として入れて、「~/doodles/dragon.jpg の絵を3Dにして空を飛ばして」のように頼みます。

```bash
git clone https://github.com/skyzhao3q/doodle-to-3d-skill.git ~/.claude/skills/doodle-to-3d
```

**Codex** などその他のエージェント：クローンしたリポジトリの中でエージェントを起動すると、`AGENTS.md` から `SKILL.md` の手順を読みます。Skill に対応したバージョンの Codex なら、フォルダごと Skill として読み込むこともできます（例：`~/.codex/skills/doodle-to-3d`）。

エージェントは `SKILL.md` に沿って進め、形が何か分からないところ（耳なのか翼なのか、など）は**推測せずにあなたに聞きます**。子どもの絵は、描いた本人に聞かないと分からないことが多いからです。

## 手で実行する

```bash
WORK=~/doodles/dragon            # 絵ごとの作業フォルダ（このリポジトリの外に置く）
mkdir -p $WORK/input && cp photo.jpg $WORK/input/
cp examples/purple-dragon/config.json $WORK/config.json   # 例をもとに書き換える

python3 scripts/prepare.py $WORK --card          # --card：机の上のカードや紙を撮った場合
python3 scripts/gem.py extract $WORK             # Gemini：キャラの取り出し（1回）
python3 scripts/cutout.py $WORK
python3 scripts/grid.py $WORK                    # 座標を読んで config.json の parts を書く
python3 scripts/parts.py $WORK                   # renders/parts_preview.png と parts_sheet.png を確認
python3 scripts/gem.py sky $WORK && python3 scripts/clouds.py $WORK                 # Gemini：空（1回）
python3 scripts/gem.py fire $WORK && python3 scripts/fire_frames.py $WORK           # Gemini：炎（1回）

blender -b -P scripts/flight.py -- $WORK build fire                 # swoop / hover も可
blender -b $WORK/out/flight_fire.blend -P scripts/flight.py -- $WORK render
blender -b $WORK/out/flight_fire.blend -P scripts/sfx_cues.py -- $WORK
python3 scripts/sfx.py $WORK flight_fire                          # swoop は --whoosh を付ける
python3 scripts/make_video.py $WORK flight_fire                   # -> out/flight_fire_sfx.mp4
python3 scripts/freeze.py $WORK v1                                # 任意：読み取り専用の素材保存
```

`config.json` の書き方は [docs/CONFIG.md](docs/CONFIG.md)（英語）にあります。例の設定はトレーディングカードに描かれた紫のドラゴン用で、座標はその絵にしか合わないので、ひな形として使ってください。

## プライバシー

- 絵は、取り出し・空・炎の3つの手順で Google の Gemini API に送られます。描いた本人（お子さんの場合は保護者も）に確認してから使ってください。データの扱いは Gemini の利用規約を確認してください。
- 作業フォルダはこのリポジトリの外に置いてください。`.gitignore` で画像・動画・音声・`.blend`・`.env` は除外していますが、それだけに頼らないでください。
- `docs/images/` の絵と GIF は、作者の家族の了承を得て掲載しているサンプルです。

## 制限

- パーツの輪郭は、絵ごとに人（またはエージェント）が座標で指定します。自動の領域分割はありません。
- 3D は絵をふくらませた「層」なので、正面から ±40° くらいまでがきれいに見える範囲です。
- 効果音は合成した簡単なものです。公開する前に一度聞いてください。
- レンダリングは 1080×1920・Eevee で、最近のノートPCで1フレーム約1秒です。

## ライセンス

MIT（[LICENSE](LICENSE)）。`docs/images/` のサンプル画像は説明用で、ほかの用途への再利用はご遠慮ください。
