"""registry.py — 動画の種類の一覧と、投稿用テキスト（タイトル・説明・タグ）の生成"""

import sims_3d
import sims_arena
import sims_board
import sims_course
import sims_light
import sims_more
import sims_pack
import sims_ring
import sims_squeeze
import sims_tower

SIMS = {
    "grow": {
        "run": sims_ring.run_grow, "length": (22, 45), "ja": "バウンドするたびに大きくなるボール（当たるたびに曲が進む）",
        "titles": ["ボールが跳ねるたびに大きくなる", "Ball gets bigger every bounce"],
    },
    "rings": {
        "run": sims_ring.run_rings, "length": (20, 40), "ja": "回転するリングのすき間から脱出",
        "titles": ["このボールは脱出できるのか", "Can the ball escape 10 rings?"],
    },
    "multiply": {
        "run": sims_ring.run_multiply, "length": (20, 40), "ja": "脱出するたびにボールが 2 個増える",
        "titles": ["脱出するたびに2個増える", "Every escape = 2 new balls"],
    },
    "colorwar": {
        "run": sims_arena.run_colorwar, "length": (38, 39), "search": False, "ja": "4 色の陣取り合戦",
        "titles": ["どの色が勝つ？陣取り合戦", "Which color takes over?"],
    },
    "battle": {
        "run": sims_arena.run_battle, "length": (22, 42), "ja": "HP 制のボールバトル（最後の 1 個が勝ち）",
        "titles": ["最後まで残るのは何色？", "Last ball standing wins"],
    },
    "marble": {
        "run": sims_3d.run_marble, "length": (18, 40), "search": False, "heavy": True, "ja": "8 色の 3D マーブルレース（ギミックの並びは毎回変わる）",
        "titles": ["何色が1位になる？マーブルレース", "Pick a color! Marble race"],
    },
    "hammer": {
        "run": sims_squeeze.run_hammer, "length": (26, 40), "ja": "左右のピストンと壁にはさまれたボールが 2 個に増える",
        "titles": ["叩き潰されると2倍", "Smashed = x2"],
    },
    "cam": {
        "run": sims_squeeze.run_cam, "length": (20, 34), "ja": "3 つのローラーと壁にはさまれたボールが 2 個に増える。回転はだんだん速くなる",
        "titles": ["はさまれると2倍", "Pinched = x2"],
    },
    "chime": {
        "run": sims_3d.run_chime, "length": (15, 45), "search": False, "heavy": True, "ja": "3D。鉄琴の上をボールが跳ねて曲を鳴らす",
        "titles": ["ボールが鉄琴で「{song}」を弾く", "A ball plays {song} on a glockenspiel"],
    },
    "towers": {
        "run": sims_tower.run_towers, "length": (30, 55), "search": False, "ja": "条件の違う 3 つの塔。10 階を最初に壊すのは？",
        "titles": ["3つの塔、10階を最初に壊すのは？", "3 towers, 3 rules - who breaks floor 10 first?"],
    },
    "faces": {
        "run": sims_3d.run_faces, "length": (15, 30), "search": False, "heavy": True, "ja": "面の数が違う布を落として比べる（16 → 4096 面）",
        "titles": ["16面と4096面、布はどう変わる？", "16 faces vs 4096 faces"],
    },
    "music": {
        "run": sims_course.run_music, "length": (10, 60), "search": False, "ja": "曲に合わせて跳ねるボール（1 バウンド = 1 音）",
        "titles": ["ボールが跳ねると「{song}」になる", "{song} but every bounce is a note"],
    },
    "weapon": {
        "run": sims_more.run_weapon, "length": (18, 42), "ja": "武器を持ったボールの 1 対 1（当てるたびに強くなる）",
        "titles": ["{vs} どっちが勝つ？", "{vs} - who wins?"],
    },
    "bricks": {
        "run": sims_more.run_bricks, "length": (20, 42), "ja": "ブロックを掘り進むレース（4 色）",
        "titles": ["最初に掘り抜くのは何色？", "First to break through wins"],
    },
    # ここから下はボール同士が押し合う「ぎっしり系」。長さがほぼ一定なのでシード探しは不要
    "fill": {
        "run": sims_pack.run_fill, "length": (25, 40), "search": False, "ja": "1 個のボールが増え続けて円を埋め尽くす",
        "titles": ["1個のボールが円を埋め尽くすまで", "1 ball fills the whole circle"],
    },
    "gear": {
        "run": sims_pack.run_gear, "length": (27, 40), "ja": "歯車の2本のアームに挟まれて潰されたボールが2個に増える",
        "titles": ["挟まれると2倍", "Squeezed = x2"],
    },
    "arms": {
        "run": sims_pack.run_arms, "length": (24, 36), "ja": "四隅のアームと壁に挟まれて潰されたボールが2個に増える",
        "titles": ["潰されると2倍", "Squeezed = x2"],
    },
    "glass": {
        "run": sims_pack.run_glass, "length": (24, 40), "ja": "右の砲台がガラスを撃つ。当たったボールは消えてガラスが欠け、外れてくぼみに落ちたボールは倍率ぶん増えて撃ち直される",
        "titles": ["ガラス100%、いつ割れる？", "Glass 100% - how long does it last?"],
    },
    "walls": {
        "run": sims_board.run_walls, "length": (15, 40), "search": False, "ja": "王冠を目指して壁で邪魔し合う盤上ゲーム",
        "titles": ["あと1歩で壁を置かれる", "First to the crown wins"],
    },
    "rays": {
        "run": sims_light.run_rays, "length": (30, 36), "search": False, "ja": "鏡の中で倍々に増える光線",
        "titles": ["光線が倍々に増えていく", "Light rays double every round"],
    },
}

# ---------------------------------------------------------------- 投稿用の文面
# タイトルは動画ごとに言い回しを変える（同じ題名の連投は、検索でも量産判定でも不利）。
# 先頭に「何の動画か」が分かる語を置き、結果は書かない（最後まで見てもらうため）。
COPY = {
    "weapon": {
        "en": ["{A} vs {B} - who wins?", "{A} or {B}? Pick one before it starts",
               "{A} vs {B} but every hit makes them stronger"],
        "ja": ["{Aj} vs {Bj} どっちが勝つ？", "{Aj}と{Bj}、強いのはどっち？", "当てるたび強くなる {Aj} vs {Bj}"],
        "rule_en": "Two balls, two weapons. Every hit powers up the weapon. First to 0 HP loses.",
        "rule_ja": "武器を持ったボールの1対1。当てるたびに武器が強くなり、HPが0になった方が負け。",
        "ask_en": "Who did you pick? Tell me the next matchup in the comments.",
        "ask_ja": "どっちを選んだ？次に見たい対戦カードはコメントで。",
        "hash": ["#ballbattle", "#weaponball"], "keys": ["ball battle", "weapon ball", "1v1", "ボール バトル"],
    },
    "colorwar": {
        "en": ["9 balls now, or x2 every 8.5 seconds?", "More balls or faster growth - which one wins?",
               "Each color starts with a different rule"],
        "ja": ["最初から9個か、8.5秒ごとに2倍か", "数が多い色と、増えるのが速い色。勝つのは？", "色ごとに条件が違う陣取り合戦"],
        "rule_en": "Each ball paints the tiles it touches. Every color starts with a different rule: "
                   "9 balls that never grow, 5 balls +1 every 7s, 2 balls +1 every 4s, or 1 ball that doubles every 8.5s. "
                   "The biggest territory when the timer ends wins.",
        "rule_ja": "ボールが触れたマスを自分の色に塗り替える陣取り合戦。色ごとに条件が違います："
                   "9個で増えない／5個で7秒ごとに+1／2個で4秒ごとに+1／1個で8.5秒ごとに2倍。時間切れで一番広い色が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#territorywar", "#colorbattle"], "keys": ["territory war", "color battle", "陣取り", "陣取り合戦"],
    },
    "bricks": {
        "en": ["First to break through wins", "Which color digs through first?", "Pick a color - brick breaker race"],
        "ja": ["最初に掘り抜くのは何色？", "ブロック崩しレース、何色が勝つ？", "色を選んで。ブロック掘りレース"],
        "rule_en": "Four balls, same wall of bricks. The first one to dig to the bottom wins.",
        "rule_ja": "4色のボールが同じ並びのブロックを掘り進むレース。最初に下まで抜けた色が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#brickbreaker", "#ballrace"], "keys": ["brick breaker", "ball race", "ブロック崩し", "レース"],
    },
    "marble": {
        "en": ["Pick a color! Marble race", "8 marbles, 1 winner - which color?", "Marble race - did your color win?"],
        "ja": ["何色が1位？マーブルレース", "8色のマーブルレース、勝つのは？", "色を選んでから見て。マーブルレース"],
        "rule_en": "Eight marbles race down a course of ramps, pegs, spinners, hammers and a big wheel. "
                   "The course is different every time. First across the line wins.",
        "rule_ja": "8色のビー玉が、坂・釘・回る羽根・ハンマー・水車のコースを下るレース。コースは毎回変わります。最初にゴールした色が勝ち。",
        "ask_en": "Did your color win?", "ask_ja": "選んだ色は勝った？",
        "hash": ["#marblerace", "#marbles"], "keys": ["marble race", "marble run", "マーブルレース", "ビー玉"],
    },
    "hammer": {
        "en": ["Smashed = x2", "1 ball, 2 pistons", "How fast does 1 ball become 320?"],
        "ja": ["叩き潰されると2倍", "ボール1個と、2本のピストン", "1個が320個になるまで"],
        "rule_en": "Two pistons take turns slamming the side walls: top, middle, bottom. "
                   "A ball caught between a piston and the wall splits in two.",
        "rule_ja": "2本のピストンが、上・中・下の順に左右の壁を交互に叩きます。ピストンと壁にはさまれたボールは2個に増えます。",
        "ask_en": "How many seconds did you guess?", "ask_ja": "何秒かかると思った？",
        "hash": ["#ballsimulation", "#asmr"], "keys": ["ball simulation", "asmr", "multiply", "ボール 増える"],
    },
    "cam": {
        "en": ["Pinched = x2", "1 ball, 3 rollers, and they keep getting faster", "How fast does 1 ball become 320?"],
        "ja": ["はさまれると2倍", "ボール1個と、だんだん速くなる3つのローラー", "1個が320個になるまで"],
        "rule_en": "Three rollers run around the inside of the ring, faster and faster. "
                   "A ball pinched between a roller and the wall splits in two.",
        "rule_ja": "3つのローラーが壁すれすれを回り、だんだん速くなります。ローラーと壁にはさまれたボールは2個に増えます。",
        "ask_en": "How many seconds did you guess?", "ask_ja": "何秒かかると思った？",
        "hash": ["#ballsimulation", "#satisfying"], "keys": ["ball simulation", "satisfying", "multiply", "ボール 増える"],
    },
    "chime": {
        "en": ["A ball plays {song} on a glockenspiel", "{song}, one bounce at a time", "{song} but every bounce is a note"],
        "ja": ["ボールが鉄琴で「{songj}」を弾く", "1バウンド1音で「{songj}」", "鉄琴の上を跳ねて「{songj}」"],
        "rule_en": "Every bar is tuned to one note. The ball lands on the next bar exactly on the beat.",
        "rule_ja": "鍵盤は1枚ずつ音が決まっています。ボールは拍に合わせて、次の鍵盤へちょうど着地します。",
        "ask_en": "Which song should the ball play next?", "ask_ja": "次に弾いてほしい曲はコメントで。",
        "hash": ["#satisfying", "#classicalmusic"], "keys": ["glockenspiel", "music ball", "marble music", "鉄琴 ボール"],
    },
    "towers": {
        "en": ["3 towers, 3 rules - who breaks floor 10 first?", "x3 per floor vs x2 per floor vs a huge head start",
               "Few balls that triple, or hundreds from the start?"],
        "ja": ["3つの塔、10階を最初に壊すのは？", "階ごとに3倍か、2倍か、最初から大勢か", "少数で3倍ずつ増えるか、最初から数百個か"],
        "rule_en": "Every hit takes 1 HP off the floor, and each floor is tougher than the one above. "
                   "The towers start with different numbers of balls and grow by different rules each time a floor breaks.",
        "rule_ja": "ボールが床に当たるたびに床の体力が1減り、下の階ほど固くなります。"
                   "塔ごとに最初の個数と、床を壊したときの増え方が違います。",
        "ask_en": "Which tower did you pick?", "ask_ja": "どの塔を選んだ？",
        "hash": ["#simulation", "#satisfying"], "keys": ["simulation race", "exponential growth", "tower", "倍々"],
    },
    "faces": {
        "en": ["16 faces vs 4096 faces", "Same cloth, more faces every time", "How many faces until it looks like cloth?"],
        "ja": ["16面と4096面、布はどう変わる？", "同じ布、面の数だけを増やしていく", "何面あれば布に見える？"],
        "rule_en": "The same square sheet is dropped five times. Only the number of faces changes: 16, 64, 256, 1024, 4096.",
        "rule_ja": "同じ大きさの四角い布を5回落とします。変えているのは面の数だけ（16・64・256・1024・4096）。",
        "ask_en": "Which one looked best to you?", "ask_ja": "どれが一番気持ちよかった？",
        "hash": ["#clothsimulation", "#3danimation"], "keys": ["cloth simulation", "3d simulation", "blender", "布 シミュレーション"],
    },
    "music": {
        "en": ["{song} but every bounce is a note", "A ball plays {song}", "{song} played by a bouncing ball"],
        "ja": ["ボールが跳ねると「{songj}」になる", "ボールが演奏する「{songj}」", "1バウンド1音で「{songj}」"],
        "rule_en": "Every time the ball hits a bar, it plays the next note.",
        "rule_ja": "ボールが板に当たるたびに、曲が1音ずつ進みます。",
        "ask_en": "Which song should the ball play next?", "ask_ja": "次に弾いてほしい曲はコメントで。",
        "hash": ["#bouncingball", "#classicalmusic"], "keys": ["bouncing ball music", "music ball", "ボール 演奏"],
    },
    "battle": {
        "en": ["Last ball standing wins", "6 balls, 1 survivor - pick one", "Which color survives?"],
        "ja": ["最後まで残るのは何色？", "6個のボール、生き残るのは1個だけ", "色を選んで。ボールのサバイバル"],
        "rule_en": "Six balls lose HP every time they collide. The arena keeps shrinking. Last one alive wins.",
        "rule_ja": "ぶつかるたびにHPが減る6個のボール。枠はだんだん狭くなり、最後に残った1個が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#ballbattle", "#battleroyale"], "keys": ["ball battle", "battle royale", "ボール バトル", "サバイバル"],
    },
    "multiply": {
        "en": ["Every escape = 2 new balls", "1 ball becomes 220", "Each ball that escapes adds 2 more"],
        "ja": ["脱出するたびに2個増える", "1個のボールが220個になるまで", "逃げるたびに増えるボール"],
        "rule_en": "Every ball that escapes the ring spawns two more inside. It starts with one.",
        "rule_ja": "リングから1個脱出するたびに、中に2個増えます。最初は1個だけ。",
        "ask_en": "How many did you expect?", "ask_ja": "何個まで増えると思った？",
        "hash": ["#bouncingball", "#ballescape"], "keys": ["bouncing ball", "ball escape", "ボール 増殖", "増える"],
    },
    "rings": {
        "en": ["Can the ball escape 10 rings?", "10 spinning rings, 1 ball", "How long until it escapes?"],
        "ja": ["このボールは脱出できる？", "回るリング10枚から脱出", "脱出まで何秒かかる？"],
        "rule_en": "One ball, ten spinning rings, one gap in each.",
        "rule_ja": "回転する10重のリング。すき間を抜けるたびにリングが1枚消えます。",
        "ask_en": "Guess the time before it ends.", "ask_ja": "脱出まで何秒か、予想してから見て。",
        "hash": ["#ballescape", "#bouncingball"], "keys": ["ball escape", "bouncing ball", "ボール 脱出", "リング"],
    },
    "grow": {
        "en": ["Ball gets bigger every bounce", "It grows until it fills the circle",
               "{song} but the ball keeps growing"],
        "ja": ["跳ねるたびに大きくなるボール", "円いっぱいになるまで大きくなる", "跳ねるたびに「{songj}」が進む"],
        "rule_en": "The ball grows with every bounce, and every bounce plays the next note.",
        "rule_ja": "跳ねるたびにボールが大きくなり、当たるたびに曲が1音進みます。",
        "ask_en": "How many bounces did you guess?", "ask_ja": "何回で埋まると思った？",
        "hash": ["#bouncingball", "#oddlysatisfying"], "keys": ["bouncing ball", "growing ball", "ボール 大きくなる"],
    },
}
COPY.update({
    "fill": {
        "en": ["1 ball fills the whole circle", "It multiplies until the circle bursts",
               "How many balls fit in one circle?"],
        "ja": ["1個のボールが円を埋め尽くすまで", "増え続けて円が弾ける", "この円にボールは何個入る？"],
        "rule_en": "Every ball keeps splitting in two. The wedge grows until the circle can't hold them.",
        "rule_ja": "ボールが2個に分かれ続け、扇形が広がっていきます。円に入りきらなくなると弾けます。",
        "ask_en": "Guess the final count before it bursts.", "ask_ja": "弾けるまでに何個になるか、予想してから見て。",
        "hash": ["#ballsimulation", "#asmr"], "keys": ["ball simulation", "asmr", "multiply", "ボール 増える"],
    },
    "gear": {
        "en": ["Squeezed = x2", "1 ball, 2 arms, and a circle that fills up", "Every squeeze makes it worse"],
        "ja": ["挟まれると2倍", "ボール1個と2本のアーム、いっぱいになる円", "潰されるたびに増えていく"],
        "rule_en": "Two arms spin in opposite directions. A ball squeezed between them splits in two, "
                   "and the new balls take the color of that moment.",
        "rule_ja": "2本のアームが逆向きに回っています。すれ違うアームに挟まれて潰されたボールは2個に増え、その瞬間の色になります。",
        "ask_en": "Which color took over the most?", "ask_ja": "一番広がったのは何色？",
        "hash": ["#ballsimulation", "#satisfying"], "keys": ["ball simulation", "satisfying", "multiply", "ボール 増える"],
    },
    "arms": {
        "en": ["Squeezed = x2", "1 ball, 4 spinning arms", "How fast does 1 ball become 320?"],
        "ja": ["潰されると2倍", "ボール1個と、回る4本のアーム", "1個が320個になるまで"],
        "rule_en": "Four arms spin on the corners of the box. A ball squeezed between an arm and a wall splits in two.",
        "rule_ja": "箱の四隅でアームが回っています。アームと壁のあいだに挟まれて潰されたボールは2個に増えます。",
        "ask_en": "How many seconds did you guess?", "ask_ja": "何秒かかると思った？",
        "hash": ["#ballsimulation", "#asmr"], "keys": ["ball simulation", "asmr", "multiply", "ボール 増える"],
    },
    "walls": {
        "en": ["First to the crown wins", "One step away... then a wall", "4 balls, 1 crown, and a lot of walls"],
        "ja": ["王冠に最初に着くのは何色？", "あと1歩で壁を置かれる", "4色のボールと1つの王冠"],
        "rule_en": "Each turn a ball either moves one square or places a wall. "
                   "Walls can slow rivals down but can never seal the crown off completely.",
        "rule_ja": "自分の番では「1マス進む」か「壁を1枚置く」。壁で相手を遠回りさせられますが、道を完全にふさぐことはできません。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#boardgame", "#satisfying"], "keys": ["board game", "maze", "strategy", "壁 ゲーム"],
    },
    "rays": {
        "en": ["Light rays double every round", "1 light ray becomes 2048", "2048 light rays inside a mirror"],
        "ja": ["光線が倍々に増えていく", "1本の光が2048本になるまで", "鏡の中で2048本の光が作る模様"],
        "rule_en": "A pulse of light bounces around inside a mirrored shape. Every round doubles the number of rays.",
        "rule_ja": "鏡でできた器の中で、光が反射を繰り返します。回を重ねるごとに光線の数が2倍になります。",
        "ask_en": "Which round looked best?", "ask_ja": "何本のときが一番きれいだった？",
        "hash": ["#lightrays", "#oddlysatisfying"], "keys": ["light rays", "reflection", "caustics", "光 反射"],
    },
    "glass": {
        "en": ["Glass 100% - how long does it last?", "1 cannon vs a wall of glass",
               "Every miss comes back x2, x3, x4... or x10"],
        "ja": ["ガラス100%、いつ割れる？", "砲台1つ対ガラスの壁", "外れた弾は x2・x3・x4、ときどき x10 で戻ってくる"],
        "rule_en": "One cannon, always in the same spot. A ball that hits the glass breaks off a piece and disappears. "
                   "A ball that misses falls into a pocket, multiplies by its number, and gets fired again.",
        "rule_ja": "砲台はいつも同じ場所。ガラスに当たったボールは、かけらを削って消えます。"
                   "外れたボールはくぼみに落ち、その数字の分だけ増えて、もう一度撃たれます。",
        "ask_en": "How many balls at the end?", "ask_ja": "最後は何個になる？",
        "hash": ["#ballsimulation", "#asmr"], "keys": ["ball simulation", "asmr", "multiplier", "ガラス"],
    },
})
COMMON_HASH = ["#shorts", "#satisfying", "#simulation", "#物理演算", "#シミュレーション"]
COMMON_KEYS = ["shorts", "satisfying", "simulation", "physics simulation", "物理演算", "シミュレーション"]
WEAPON_JA = {"SWORD": "剣", "DAGGER": "短剣", "SPEAR": "槍", "HAMMER": "ハンマー"}


def _fill(text, meta):
    song = meta.get("song") or {}
    a, _, b = (meta.get("title_extra") or " vs ").partition(" vs ")
    return (text.replace("{A}", a).replace("{B}", b)
            .replace("{Aj}", WEAPON_JA.get(a, a)).replace("{Bj}", WEAPON_JA.get(b, b))
            .replace("{song}", song.get("title", "")).replace("{songj}", song.get("title_ja", song.get("title", ""))))


def post_meta(name, meta, seed=0):
    """投稿に使う文面一式。

    タイトルは英語を基本にし、日本語版は YouTube の「翻訳」機能（localizations）で日本の視聴者にだけ出す。
    ハッシュタグは種類を表すものを先頭に置く（YouTube は先頭 3 個をタイトルの上に表示する）。"""
    c = COPY[name]
    k = int(seed) % len(c["en"])
    en, ja = _fill(c["en"][k], meta), _fill(c["ja"][k], meta)
    song = meta.get("song")
    credit_en = f"Music: {song['title']} / {song['composer']} (public domain, synthesized)" if song else ""
    credit_ja = f"曲: {song.get('title_ja', song['title'])}（{song['composer']}、著作権切れ。音は自作の合成音）" if song else ""
    tags_line = " ".join(dict.fromkeys(c["hash"] + COMMON_HASH))       # 同じタグを 2 回書かない
    desc_en = "\n".join(x for x in [c["rule_en"], c["ask_en"], credit_en, "", tags_line] if x is not None)
    desc_ja = "\n".join(x for x in [c["rule_ja"], c["ask_ja"], credit_ja, "", tags_line] if x is not None)
    desc_en = desc_en.replace("\n\n\n", "\n\n")
    desc_ja = desc_ja.replace("\n\n\n", "\n\n")
    # TikTok と X は世界向けに英語のみ。
    # X はタイムラインで動画の上に出る 1 行だけにする（ハッシュタグは X では効果が薄く、宣伝っぽく見える）
    tiktok = f"{en}\n{' '.join(dict.fromkeys(c['hash'] + ['#satisfying', '#simulation', '#fyp']))}"
    x_post = en
    return {"type": name, "label_ja": SIMS[name]["ja"], "title": en, "description": desc_en,
            "title_ja": ja, "description_ja": desc_ja, "tags": list(dict.fromkeys(c["keys"] + COMMON_KEYS)),
            "tiktok_caption": tiktok, "x_post": x_post}


def post_text(name, meta, duration, seed=0):
    m = post_meta(name, meta, seed)
    lines = ["【YouTube タイトル】", m["title"], "", "【YouTube 説明文】", m["description"], "",
             "【日本語版のタイトル】", m["title_ja"], "", "【日本語版の説明文】", m["description_ja"], "",
             "【TikTok の説明欄】", m["tiktok_caption"], "", "【X の投稿文】", m["x_post"], "",
             f"長さ: {duration:.1f}秒 / 結果: {meta.get('result', '-')}", ""]
    return "\n".join(lines)
