const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });

module.exports = {
    server: {
        port: process.env.PORT || 3000
    },
    ollama: {
        baseUrl: process.env.OLLAMA_BASE_URL || 'http://localhost:11434',
        apiKey: process.env.OLLAMA_API_KEY,
        defaultContext: 131072,
        systemMessage: {
            manager: `You are a helpful legal assistant interface. 
Your goal is to understand the user's question and allow your specialized research agent to find the answers.
You have access to a tool called 'delegate_research'. 
- IF the user asks a question about UK legislation, case law, or legal concepts, you MUST used 'delegate_research' to get the answer.
- Do not try to answer legal questions yourself without using the tool.
- If the tool returns an answer, summarize it for the user politely.
- IMPORTANT: You MUST preserve all source URLs and citations provided by the research agent in your final summary. The user relies on these links.
- If the user just says hello or asks a general non-legal question, answer normally without tools.`,
            worker: `You are a strict legal research assistant for UK law.
Your answers must be grounded EXCLUSIVELY in the data you retrieve from the Lex API.
When you cite legislation or case law, you MUST provide the source URL if available.
- For Legislation: The tools return a 'uri' field. Use this to create a Markdown link: [Title](uri).
- For Case Law: If a URL is provided, use it. If not, cite the case name and citation clearly.`
        }
    },
    lexApi: {
        url: process.env.LEX_API_URL || 'https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io'
    },
    models: [
        { name: 'mistral-large-3:675b-cloud', contextLengthKB: 256 },
        { name: 'cogito-2.1:671b-cloud', contextLengthKB: 160 },
        { name: 'kimi-k2-thinking:cloud', contextLengthKB: 256 },
        { name: 'minimax-m2:cloud', contextLengthKB: 200 },
        { name: 'qwen3-coder:480b-cloud', contextLengthKB: 256 },
        { name: 'deepseek-v3.1:671b-cloud', contextLengthKB: 160 },
        { name: 'glm-4.6:cloud', contextLengthKB: 198 },
        { name: 'gpt-oss:120b-cloud', contextLengthKB: 128 }
    ]
};
