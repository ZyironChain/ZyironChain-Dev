






class Constants:

    # 🔹 **Genesis Block Target (Ultra Easy - Mines Instantly for SHA3-384)**
    GENESIS_TARGET = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 🔥 Extremely easy for first few blocks

    # 🔹 **Minimum Difficulty (Ensures rapid early mining)**
    MIN_DIFFICULTY = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 🚀 Ensures first blocks are mined instantly

    # 🔹 **Maximum Difficulty (For long-term scaling)**
    MAX_DIFFICULTY = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 🚧 Absolute max cap

    # 🔹 **Difficulty Adjustment Parameters**
    TARGET_BLOCK_TIME = 300  # ⏳ **Target Block Time**: 5 minutes
    DIFFICULTY_ADJUSTMENT_INTERVAL = 2  # 🔄 **Adjust every 2 blocks** (ensures quick scaling)
    MIN_DIFFICULTY_FACTOR = 0.85  # ⬇️ **Difficulty can decrease by up to 15%**
    MAX_DIFFICULTY_FACTOR = 4.0  # ⬆️ **Difficulty can increase up to 400%**

    # 🔹 **Zero Hash (Used for Genesis Block and Empty Hashes)**
    ZERO_HASH = "0" * 96  # SHA3-384 produces **96-character hex hashes**
    
    MAX_SUPPLY = 84096000
    INTIAL_COINBASE_REWARD = 100.00 
    BLOCKCHAIN_HALVING_BLOCK_HEIGHT = 420480


