"""registry.py — 動画の種類の一覧と、投稿用テキスト（タイトル・説明・タグ）の生成"""

import sims_3d
import sims_arena
import sims_board
import sims_course
import sims_fill
import sims_light
import sims_more
import sims_pack
import sims_party
import sims_ring
import sims_squeeze
import sims_swarm
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
    "bricks2": {
        "run": sims_more.run_bricks2, "length": (20, 40), "search": False, "ja": "条件の違うブロック掘りレース（強い 1 個／2 個／弱い 6 個）",
        "titles": ["強い1個か、弱い6個か。先に掘り抜くのは？", "1 strong ball vs 6 weak ones - who digs through first?"],
    },
    "hexarms": {
        "run": sims_squeeze.run_hexarms, "length": (24, 36), "ja": "六角形の中で 3 本のアームが回り、壁とのあいだで潰されたボールが 2 個に増える",
        "titles": ["六角形の中で、潰されると2倍", "Squeezed = x2 (hexagon)"],
    },
    "beams": {
        "run": sims_squeeze.run_beams, "length": (22, 42), "ja": "緑の光線に触れると 2 倍、赤の光線に触れると消える",
        "titles": ["緑で2倍、赤で消える", "GREEN = x2, RED = gone"],
    },
    "rps": {
        "run": sims_swarm.run_rps, "length": (20, 41), "ja": "グー・チョキ・パーの駒が追いかけ合い、触れた相手を仲間に変える",
        "titles": ["グー・チョキ・パー、最後に残るのは？", "Rock Paper Scissors - which one takes over?"],
    },
    "colorwar2": {
        "run": sims_arena.run_colorwar2, "length": (38, 39), "search": False, "ja": "陣取り合戦の別バージョン（大きい 1 個／速い 2 個／遅い 8 個／ふつう 4 個）",
        "titles": ["大きい1個か、速い2個か、遅い8個か", "1 giant vs 2 fast vs 8 slow vs 4 normal"],
    },
    "survive": {
        "run": sims_squeeze.run_survive, "length": (17, 30), "ja": "ローラーに潰されるたびにライフが減る生き残り戦（6 色）",
        "titles": ["潰されたらライフ-1。最後に残るのは？", "Squeezed = -1 life. Last ball wins"],
    },
    "smash": {
        "run": sims_squeeze.run_smash, "length": (20, 36), "ja": "ピストンに潰されるたびにライフが減る生き残り戦（6 色）",
        "titles": ["叩かれたらライフ-1。最後に残るのは？", "Smashed = -1 life. Last ball wins"],
    },
    "fillwave": {
        "run": sims_fill.run_fillwave, "length": (22, 40), "search": False, "ja": "形を埋め尽くしたあと、色の波が走る",
        "titles": ["いっぱいになったら、色の波", "Wait for the wave"],
    },
    "blackhole": {
        "run": sims_fill.run_blackhole, "length": (24, 42), "ja": "育っていくブラックホールから逃げる生き残り戦（8 色）",
        "titles": ["吸い込まれたら脱落。最後に残るのは？", "Don't fall in - last ball wins"],
    },
    "bomb": {
        "run": sims_party.run_bomb, "length": (24, 40), "search": False, "ja": "爆弾まわしの生き残り戦（触れると爆弾が移る。8 色）",
        "titles": ["爆弾を持ったまま時間切れで脱落。最後に残るのは？", "Hot potato - don't hold the bomb"],
    },
    "plinko": {
        "run": sims_party.run_plinko, "length": (26, 40), "search": False, "ja": "600 個のボールを釘の板に落とす（山の形ができる）",
        "titles": ["600個のボール、どこに落ちる？", "Where do 600 balls land?"],
    },
    "towers2": {
        "run": sims_tower.run_towers2, "length": (30, 50), "search": False, "ja": "3 つの塔の別バージョン（階ごとに 2 倍／毎秒増える／増えない）",
        "titles": ["倍々か、毎秒増えるか、最初から大勢か", "x2 per floor vs +82 per second vs 1,520 from the start"],
    },
    "cannons": {
        "run": sims_tower.run_cannons, "length": (30, 50), "search": False, "ja": "条件の違う 3 つの砲台。壁を最初に壊すのは？",
        "titles": ["3つの砲台、壁を最初に壊すのは？", "3 cannons, 3 rules - who breaks the wall first?"],
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
    "bricks2": {
        "en": ["1 strong ball vs 6 weak ones - who digs through first?", "Same bricks, different rules",
               "6 damage x1, 3 damage x2, or 1 damage x6?"],
        "ja": ["強い1個か、弱い6個か。先に掘り抜くのは？", "同じブロック、違う条件", "6ダメージ1個・3ダメージ2個・1ダメージ6個"],
        "rule_en": "Every lane has the same bricks. One lane gets a single ball that hits for 6, one gets two balls "
                   "that hit for 3, and one gets six balls that hit for 1. The first ball to reach the bottom wins.",
        "rule_ja": "どのレーンもブロックの並びは同じ。6ダメージのボール1個、3ダメージのボール2個、1ダメージのボール6個の3レーンで、"
                   "最初に下まで掘り抜いた色が勝ち。",
        "ask_en": "Which lane did you pick?", "ask_ja": "どのレーンを選んだ？",
        "hash": ["#brickbreaker", "#ballrace"], "keys": ["brick breaker", "ball race", "ブロック崩し", "レース"],
    },
    "hexarms": {
        "en": ["Squeezed = x2", "1 ball, 3 arms, 6 walls", "How fast does 1 ball become 320?"],
        "ja": ["潰されると2倍", "ボール1個、アーム3本、壁6枚", "1個が320個になるまで"],
        "rule_en": "Three arms spin on the corners of a hexagon. A ball squeezed between an arm and a wall splits in two.",
        "rule_ja": "六角形の角で3本のアームが回っています。アームと壁のあいだに挟まれて潰されたボールは2個に増えます。",
        "ask_en": "How many seconds did you guess?", "ask_ja": "何秒かかると思った？",
        "hash": ["#ballsimulation", "#asmr"], "keys": ["ball simulation", "asmr", "multiply", "ボール 増える"],
    },
    "beams": {
        "en": ["GREEN = x2, RED = gone", "Can 1 ball reach 300 before the red beam gets it?", "One beam doubles, one beam deletes"],
        "ja": ["緑で2倍、赤で消える", "赤い光線に消される前に、300個まで増える？", "増やす光線と、消す光線"],
        "rule_en": "A ball that touches the green beam splits in two. A ball that touches the red beam disappears. "
                   "The beams spin in opposite directions.",
        "rule_ja": "緑の光線に触れたボールは2個に増え、赤の光線に触れたボールは消えます。2本の光線は逆向きに回っています。",
        "ask_en": "Did you think it would make it?", "ask_ja": "300個まで行けると思った？",
        "hash": ["#ballsimulation", "#satisfying"], "keys": ["ball simulation", "satisfying", "multiply", "ボール 増える"],
    },
    "rps": {
        "en": ["Rock Paper Scissors - which one takes over?", "34 rocks, 34 papers, 34 scissors. One survives",
               "Everyone chases what they beat"],
        "ja": ["グー・チョキ・パー、最後に残るのは？", "グー34・チョキ34・パー34、残るのは1種類", "みんな、勝てる相手を追いかける"],
        "rule_en": "Every piece chases what it beats and runs from what beats it. A touch converts the loser. "
                   "It ends when only one kind is left.",
        "rule_ja": "どの駒も、勝てる相手を追いかけ、負ける相手から逃げます。触れられた側は相手の仲間に変わり、1種類だけになったら終わり。",
        "ask_en": "Which one did you pick?", "ask_ja": "どれを選んだ？",
        "hash": ["#simulation", "#rockpaperscissors"], "keys": ["rock paper scissors", "simulation", "battle", "じゃんけん"],
    },
    "colorwar2": {
        "en": ["1 giant vs 2 fast vs 8 slow vs 4 normal", "Size, speed or numbers - which one takes the map?",
               "One giant ball against eight slow ones"],
        "ja": ["大きい1個か、速い2個か、遅い8個か", "大きさ・速さ・数、陣地を取るのはどれ？", "巨大な1個 対 遅い8個"],
        "rule_en": "Each ball paints the tiles it touches. Every color plays differently: one giant fast ball, "
                   "two fast balls, eight slow balls, or four normal ones. The biggest territory when the timer ends wins.",
        "rule_ja": "ボールが触れたマスを自分の色に塗り替える陣取り合戦。色ごとに戦い方が違います："
                   "巨大で速い1個／速い2個／遅い8個／ふつうの4個。時間切れで一番広い色が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#territorywar", "#colorbattle"], "keys": ["territory war", "color battle", "陣取り", "陣取り合戦"],
    },
    "survive": {
        "en": ["Squeezed = -1 life. Last ball wins", "6 balls, 5 lives each, 3 rollers", "Pick a color before the rollers speed up"],
        "ja": ["潰されたらライフ-1。最後に残るのは？", "6個のボール、ライフ5、ローラー3つ", "ローラーが速くなる前に色を選んで"],
        "rule_en": "Three rollers run around the ring, faster and faster. A ball pinched between a roller and the wall "
                   "loses a life. The last ball left wins.",
        "rule_ja": "3つのローラーが壁ぎわを回り、だんだん速くなります。ローラーと壁にはさまれたボールはライフが1減り、最後に残った1個が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#ballrace", "#satisfying"], "keys": ["ball race", "last ball standing", "survival", "ボール サバイバル"],
    },
    "smash": {
        "en": ["Smashed = -1 life. Last ball wins", "6 balls, 4 lives each, 2 pistons", "Pick a color - who survives the pistons?"],
        "ja": ["叩かれたらライフ-1。最後に残るのは？", "6個のボール、ライフ4、ピストン2本", "色を選んで。ピストンから生き残るのは？"],
        "rule_en": "Two pistons take turns slamming the side walls. A ball caught between a piston and the wall "
                   "loses a life. The last ball left wins.",
        "rule_ja": "2本のピストンが左右の壁を交互に叩きます。ピストンと壁にはさまれたボールはライフが1減り、最後に残った1個が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#ballrace", "#satisfying"], "keys": ["ball race", "last ball standing", "survival", "ボール サバイバル"],
    },
    "fillwave": {
        "en": ["Wait for the wave", "Fill it up, then watch the colors line up", "Every wall hit = +1... until it's full"],
        "ja": ["いっぱいになったら、色の波", "埋め尽くしたあと、色がそろう", "壁に当たるたびに+1、いっぱいになるまで"],
        "rule_en": "Every ball that hits the wall adds one more. When the shape is full, a wave sorts the colors.",
        "rule_ja": "壁に当たるたびにボールが1個増えます。形がいっぱいになると、色の波が走って虹色に並びます。",
        "ask_en": "Which shape should be next?", "ask_ja": "次はどんな形がいい？",
        "hash": ["#ballsimulation", "#satisfying"], "keys": ["ball simulation", "satisfying", "fill", "ボール 増える"],
    },
    "blackhole": {
        "en": ["Don't fall in - last ball wins", "8 balls vs a growing black hole", "Pick a color before the hole gets bigger"],
        "ja": ["吸い込まれたら脱落。最後に残るのは？", "8個のボール対、育つブラックホール", "穴が大きくなる前に色を選んで"],
        "rule_en": "The black hole in the middle keeps growing and pulling. A ball that touches it is out. The last ball left wins.",
        "rule_ja": "まん中のブラックホールが育ちながらボールを引き寄せます。触れたボールは脱落。最後に残った1個が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#ballrace", "#blackhole"], "keys": ["ball race", "black hole", "survival", "ブラックホール"],
    },
    "bomb": {
        "en": ["Hot potato - don't hold the bomb", "Touch to pass the bomb - last ball wins", "8 balls, 1 bomb, 7 explosions"],
        "ja": ["爆弾を持ったまま時間切れで脱落。最後に残るのは？", "触れたら爆弾が移る。8個の生き残り戦", "8個のボールと1個の爆弾"],
        "rule_en": "There is one bomb. The ball holding it passes it on by touching another ball. "
                   "When the fuse runs out, the holder is out, and the bomb flies to the nearest ball. The last ball left wins.",
        "rule_ja": "爆弾は1個だけ。持っているボールが別のボールに触れると爆弾が移ります。"
                   "導火線が尽きたとき持っていた色が脱落し、爆弾は一番近いボールへ飛びます。最後に残った1個が勝ち。",
        "ask_en": "Which color did you pick?", "ask_ja": "何色を選んだ？",
        "hash": ["#ballrace", "#hotpotato"], "keys": ["ball race", "hot potato", "bomb", "survival", "爆弾"],
    },
    "plinko": {
        "en": ["Where do 600 balls land?", "600 balls, 12 rows of pegs", "Drop 600 balls and watch the shape appear"],
        "ja": ["600個のボール、どこに落ちる？", "600個のボールと12段の釘", "600個落とすと、形が現れる"],
        "rule_en": "600 balls drop from the same spot. Every peg sends a ball left or right, and they pile up in 13 slots. "
                   "At the end a color wave counts each slot.",
        "rule_ja": "600個のボールを同じ場所から落とします。釘に当たるたびに左右へ分かれ、下の13個の仕切りに積もります。"
                   "最後に色の波が1列ずつ数えます。",
        "ask_en": "Did you guess the shape?", "ask_ja": "どんな形になると思った？",
        "hash": ["#plinko", "#galtonboard"], "keys": ["plinko", "galton board", "satisfying", "ピンボール", "確率"],
    },
    "towers2": {
        "en": ["x2 per floor vs +82 per second vs 1,520 from the start", "3 towers, 3 rules - who breaks floor 10 first?",
               "Doubling, steady growth, or a huge head start?"],
        "ja": ["倍々か、毎秒増えるか、最初から大勢か", "3つの塔、10階を最初に壊すのは？", "2倍ずつ・毎秒82個・最初から1,520個"],
        "rule_en": "Every hit takes 1 HP off the floor, and each floor is tougher than the one above. "
                   "One tower doubles on every floor, one gains balls every second, and one starts huge but never grows.",
        "rule_ja": "ボールが床に当たるたびに床の体力が1減り、下の階ほど固くなります。"
                   "階ごとに2倍になる塔、毎秒ボールが増える塔、最初から大勢で増えない塔の3つです。",
        "ask_en": "Which tower did you pick?", "ask_ja": "どの塔を選んだ？",
        "hash": ["#simulation", "#satisfying"], "keys": ["simulation race", "exponential growth", "tower", "倍々"],
    },
    "cannons": {
        "en": ["3 cannons, 3 rules - who breaks the wall first?", "x2 speed vs +1 cannon vs a head start",
               "One cannon that keeps doubling, or a whole row from the start?"],
        "ja": ["3つの砲台、壁を最初に壊すのは？", "速さ2倍か、1門ずつ増えるか、最初から多いか", "倍々で速くなる1門か、最初からずらりと並ぶか"],
        "rule_en": "Every shot takes 1 HP off the wall. One cannon doubles its fire rate on a timer, "
                   "one lane adds a cannon on a timer, and one lane starts with a full row that never grows.",
        "rule_ja": "1発で壁の体力が1減ります。1門だけで撃つ速さが倍々になる砲台、一定時間ごとに1門ずつ増える砲台、"
                   "最初から何門もあって増えない砲台の3つです。",
        "ask_en": "Which lane did you pick?", "ask_ja": "どのレーンを選んだ？",
        "hash": ["#simulation", "#satisfying"], "keys": ["simulation race", "exponential growth", "cannon", "倍々"],
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
