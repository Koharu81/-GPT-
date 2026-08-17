import { MiraeClient } from "../src/index.js";

const client = new MiraeClient({ apiKey: "YOUR_MIRAE_API_KEY" });
const reply = await client.reply("안녕하세요. Hello!");
console.log(reply);
