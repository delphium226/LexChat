require('dotenv').config();

module.exports = {
    server: {
        port: process.env.PORT || 3000
    },
    ollama: {
        baseUrl: process.env.OLLAMA_BASE_URL || 'http://localhost:11434',
        apiKey: process.env.OLLAMA_API_KEY,
        defaultContext: 131072,
        systemMessage: `You are a helpful legal research assistant for UK law.
When you cite legislation or case law, you MUST provide the source URL if available.
- For Legislation: The tools return a 'uri' field (e.g., http://www.legislation.gov.uk/id/...). Use this to create a Markdown link: [Title](uri).
- For Case Law: If a URL is provided, use it. If not, cite the case name and citation clearly.`
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
