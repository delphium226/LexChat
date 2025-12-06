const axios = require('axios');
const { agentLogger } = require('../utils/logger');
require('dotenv').config();

const LEX_API_URL = process.env.LEX_API_URL || 'https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io';

const tools = [
  {
    type: 'function',
    function: {
      name: 'search_legislation',
      description: 'Search for UK legislation (Acts and Statutory Instruments) by title or content.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The search query (e.g., "Computer Misuse Act", "speeding fines").',
          },
          year_from: {
            type: 'integer',
            description: 'Optional start year filter.',
          },
          year_to: {
            type: 'integer',
            description: 'Optional end year filter.',
          },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'get_legislation_text',
      description: 'Get the full text of a specific piece of legislation using its ID.',
      parameters: {
        type: 'object',
        properties: {
          legislation_id: {
            type: 'string',
            description: 'The legislation ID (e.g., "ukpga/1990/18").',
          },
        },
        required: ['legislation_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'search_caselaw',
      description: 'Search for UK court cases and judgments.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The search query (e.g., "Donoghue v Stevenson", "negligence duty of care").',
          },
          year_from: {
            type: 'integer',
            description: 'Optional start year filter.',
          },
          year_to: {
            type: 'integer',
            description: 'Optional end year filter.',
          },
        },
        required: ['query'],
      },
    },
  },
];

async function executeTool(name, args) {
  agentLogger.info(`[Tool Exec] ${name} with args: ${JSON.stringify(args)}`);
  try {
    switch (name) {
      case 'search_legislation':
        const legRes = await axios.post(`${LEX_API_URL}/legislation/search`, {
          query: args.query,
          year_from: args.year_from,
          year_to: args.year_to,
          limit: 5, // Limit to avoid context overflow
          include_text: false // Metadata only for search to save tokens
        });
        return JSON.stringify(legRes.data);

      case 'get_legislation_text':
        const textRes = await axios.post(`${LEX_API_URL}/legislation/text`, {
          legislation_id: args.legislation_id,
        });
        // Truncate if too long? For now let's hope it fits or the model handles it.
        // The API returns { legislation: {...}, full_text: "..." }
        return JSON.stringify(textRes.data);

      case 'search_caselaw':
        const caseRes = await axios.post(`${LEX_API_URL}/caselaw/search`, {
          query: args.query,
          year_from: args.year_from,
          year_to: args.year_to,
          size: 5
        });
        return JSON.stringify(caseRes.data);

      default:
        return `Error: Tool ${name} not found.`;
    }
  } catch (error) {
    agentLogger.error(`[Tool Error] ${name}: ${error.message}`);
    if (error.response) {
      agentLogger.error(`Data: ${JSON.stringify(error.response.data)}`);
      return `Error executing tool: ${JSON.stringify(error.response.data)}`;
    }
    return `Error executing tool: ${error.message}`;
  }
}

module.exports = { tools, executeTool };
