const axios = require('axios');
const { agentLogger } = require('../utils/logger');
const config = require('../config');

const LEX_API_URL = config.lexApi.url;

// Tools available to the Manager (Chat) Context
const managerTools = [
  {
    type: 'function',
    function: {
      name: 'delegate_research',
      description: 'Delegates a complex legal research task to a specialized agent. Use this for any question about UK legislation, case law, or legal concepts.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The detailed research question to ask the specialized agent.',
          },
        },
        required: ['query'],
      },
    },
  }
];

// Tools available to the Worker (Agent) Context
const workerTools = [
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

// This function only executes "Leaf" tools (Worker tools)
// The Manager's 'delegate_research' meta-tool is handled by the Agent Controller (ollama.js)
async function executeWorkerTool(name, args) {
  agentLogger.info(`[Worker Tool Exec] ${name} with args: ${JSON.stringify(args)}`);
  try {
    switch (name) {
      case 'search_legislation':
        const legRes = await axios.post(`${LEX_API_URL}/legislation/search`, {
          query: args.query,
          year_from: args.year_from,
          year_to: args.year_to,
          limit: 5,
          include_text: false
        });
        return JSON.stringify(legRes.data);

      case 'get_legislation_text':
        const textRes = await axios.post(`${LEX_API_URL}/legislation/text`, {
          legislation_id: args.legislation_id,
        });
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
        return `Error: Tool ${name} not found in worker toolset.`;
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

module.exports = { managerTools, workerTools, executeWorkerTool };
