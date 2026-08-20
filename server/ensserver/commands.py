"""Command ids, recovered from the ``Net_*REQUEST`` functions.

Each id is the ``u16`` written at offset 9 of a request.  The names follow
the symbol names still present in ``libjccvt.so``; the Korean labels are the
in-game menus those symbols drive (see ``docs/protocol.md``).
"""

# --- session / misc -------------------------------------------------------
CMD_SMS = 0x13  # Net_smsREQUEST
CMD_TIME = 0x1E  # Net_timeREQUEST         서버 시각
CMD_USER = 0x23  # Net_userREQUEST         유저 등록/로그인
CMD_CASH_IS_BUY = 0x39  # Net_cashIsBUY
CMD_CASH_BUY = 0x3A  # Net_cashBUY

# --- 우편함 / 선물 (mail & gifts) ----------------------------------------
CMD_GIFT_SEND = 0x45  # Net_gift_1REQUEST1 / 2
CMD_GIFT_INBOX = 0x46  # Net_gift_2REQUEST
CMD_GIFT_TAKE = 0x47  # Net_gift_3REQUEST
CMD_GIFT_DETAIL = 0x48  # Net_gift_4REQUEST

# --- 경매장 (auction house) ----------------------------------------------
CMD_AUCTION_SELL = 0x101  # Net_auction_1REQUEST
CMD_AUCTION_COUNT = 0x102  # Net_auction_2REQUEST
CMD_AUCTION_LIST = 0x103  # Net_auction_3REQUEST
CMD_AUCTION_CANCEL = 0x104  # Net_auction_4REQUEST
CMD_AUCTION_BUY = 0x105  # Net_auction_5REQUEST

# --- 랭킹 / 대전 (ranking & battle) --------------------------------------
CMD_RANK_REPORT = 0x111  # Net_battle_rank_1REQUEST
CMD_RANK_MINE = 0x112  # Net_battle_rank_2REQUEST
CMD_RANK_LIST = 0x113  # Net_battle_rank_3REQUEST
CMD_BATTLE_LOG_WRITE = 0x114  # Net_battle_log_1REQUEST
CMD_BATTLE_LOG_LIST = 0x115  # Net_battle_log_2REQUEST
CMD_RANK_RESULT = 0x116  # Net_battle_rank_4REQUEST

# --- 미지의 섬 (the "unknown island" content) ----------------------------
CMD_ISLAND_ENTER = 0x121  # Net_unknown_1REQUEST     입장/갱신 통보
CMD_ISLAND_COUNT = 0x122  # Net_unknown_2REQUEST     섬에 있는 인원수
CMD_ISLAND_TARGET = 0x123  # Net_unknown_3REQUEST    상대 정보 조회
CMD_ISLAND_UPDATE = 0x124  # Net_unknown_4REQUEST    내 섬 상태 등록
CMD_ISLAND_BOX = 0x125  # Net_unknown_5REQUEST       상자/획득 처리
CMD_ISLAND_LOG_WRITE = 0x126  # Net_unknown_log_1REQUEST  방문 기록 남기기
CMD_ISLAND_LOG_LIST = 0x127  # Net_unknown_log_2REQUEST   방문 기록 조회

# --- 즐겨찾기 (favourites) -----------------------------------------------
CMD_FAVORITE_ADD = 0x131  # Net_favorite_1REQUEST
CMD_FAVORITE_LIST = 0x132  # Net_favorite_2REQUEST
CMD_FAVORITE_DEL = 0x133  # Net_favorite_3REQUEST

# --- 친구 (friends) -------------------------------------------------------
CMD_FRIEND_ADD = 0x141  # Net_friend_1REQUEST
CMD_FRIEND_LIST = 0x142  # Net_friend_2REQUEST
CMD_FRIEND_DEL = 0x143  # Net_friend_3REQUEST

NAMES = {
    CMD_SMS: "sms",
    CMD_TIME: "time",
    CMD_USER: "user",
    CMD_CASH_IS_BUY: "cash_is_buy",
    CMD_CASH_BUY: "cash_buy",
    CMD_GIFT_SEND: "gift_send",
    CMD_GIFT_INBOX: "gift_inbox",
    CMD_GIFT_TAKE: "gift_take",
    CMD_GIFT_DETAIL: "gift_detail",
    CMD_AUCTION_SELL: "auction_sell",
    CMD_AUCTION_COUNT: "auction_count",
    CMD_AUCTION_LIST: "auction_list",
    CMD_AUCTION_CANCEL: "auction_cancel",
    CMD_AUCTION_BUY: "auction_buy",
    CMD_RANK_REPORT: "rank_report",
    CMD_RANK_MINE: "rank_mine",
    CMD_RANK_LIST: "rank_list",
    CMD_BATTLE_LOG_WRITE: "battle_log_write",
    CMD_BATTLE_LOG_LIST: "battle_log_list",
    CMD_RANK_RESULT: "rank_result",
    CMD_ISLAND_ENTER: "island_enter",
    CMD_ISLAND_COUNT: "island_count",
    CMD_ISLAND_TARGET: "island_target",
    CMD_ISLAND_UPDATE: "island_update",
    CMD_ISLAND_BOX: "island_box",
    CMD_ISLAND_LOG_WRITE: "island_log_write",
    CMD_ISLAND_LOG_LIST: "island_log_list",
    CMD_FAVORITE_ADD: "favorite_add",
    CMD_FAVORITE_LIST: "favorite_list",
    CMD_FAVORITE_DEL: "favorite_del",
    CMD_FRIEND_ADD: "friend_add",
    CMD_FRIEND_LIST: "friend_list",
    CMD_FRIEND_DEL: "friend_del",
}


def name(cmd: int) -> str:
    return NAMES.get(cmd, f"unknown_0x{cmd:x}")
