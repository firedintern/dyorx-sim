# DYORX Thesis

## what we are testing

savings circles (consórcios in brazil, ROSCAs globally) are one of the oldest financial tools on earth. ~1 billion people use them. they work because social pressure makes people save when they wouldn't on their own.

the problem: the money sitting in the pool earns nothing. zero yield. if 12 people contribute $100/month, at any given time there's $hundreds sitting idle.

DYORX routes that idle pool into Solana DeFi (Kamino USDC vaults, MarginFi) and earns 6-8% APY. the yield gets distributed to members. nobody needs to know they are using blockchain. they interact via WhatsApp, pay via PIX (brazil), and see their savings grow.

## the core hypothesis

> if circle members see their pooled money earning yield, dropout rates decrease and circle completion rates increase

this is the one thing we need to prove. everything else (WhatsApp UX, PIX integration, solana infra) is execution. the thesis is behavioral: do people stay longer when their money works for them?

## why simulation helps

we can't run 100 real circles before fundraising. but we can simulate 100 circles with AI agents that behave like real people: some are reliable savers, some are flaky, some hit unexpected expenses. if the sim consistently shows that yield-bearing circles outperform traditional ones on completion and total savings, that is signal.

this is not proof. it is directional evidence for investor conversations and product decisions.

## what the sim measures

→ completion rate: % of members who finish the full circle
→ dropout timing: when do people quit? earlier = worse. yield should push dropouts later
→ total contributed: more people staying = more total savings
→ yield earned: tangible $ that wouldn't exist in a traditional circle
→ behavior by personality: which member types are most affected by yields?

## expected outcome

financially stressed members (the ones who need savings circles most) are the most yield-sensitive. even $5-10/month in yield changes their mental math from "i can't afford to contribute this month" to "i lose free money if i stop."

that is the DYORX thesis in one sentence.
