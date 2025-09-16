# Component Interaction Sequence Diagrams

## Preview Operation Sequence

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as MCP Server
    participant Preview as Preview Tool
    participant JSON as JSON Processor
    participant LLM as LLM Service
    participant Session as Session Manager
    participant Redis as Redis Store
    
    Client->>Server: json_editor_preview(document, instruction)
    Server->>Preview: handle_preview_request()
    
    Note over Preview: Validate input parameters
    Preview->>JSON: json2map(document)
    JSON-->>Preview: map_entries[]
    
    Preview->>LLM: get_proposed_changes(map_entries, instruction)
    Note over LLM: Analyze instruction<br/>Identify target nodes<br/>Generate changes
    LLM-->>Preview: proposed_changes[]
    
    Preview->>Session: create_session(document, changes)
    Session->>Redis: store_session_data()
    Redis-->>Session: session_id
    Session-->>Preview: session_id
    
    Preview->>Preview: format_preview_response()
    Preview-->>Server: PreviewResponse(changes, session_id)
    Server-->>Client: MCP Response(preview_data)
```

## Apply Operation Sequence

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as MCP Server
    participant Apply as Apply Tool
    participant Session as Session Manager
    participant Redis as Redis Store
    participant JSON as JSON Processor
    
    Client->>Server: json_editor_apply(session_id, confirmed_changes)
    Server->>Apply: handle_apply_request()
    
    Apply->>Session: get_session(session_id)
    Session->>Redis: retrieve_session_data()
    Redis-->>Session: session_data
    Session-->>Apply: PreviewSession(document, changes)
    
    Note over Apply: Validate session exists<br/>Check document unchanged
    Apply->>Apply: verify_document_state()
    
    Apply->>JSON: apply_changes(document, confirmed_changes)
    Note over JSON: Apply modifications<br/>Reconstruct JSON<br/>Track applied changes
    JSON-->>Apply: modified_document, applied_changes
    
    Apply->>Apply: format_apply_response()
    Apply-->>Server: ApplyResponse(document, changes)
    Server-->>Client: MCP Response(result_data)
```

## Error Handling Sequence

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as MCP Server
    participant Tool as Tool Handler
    participant LLM as LLM Service
    participant Session as Session Manager
    
    Client->>Server: tool_request(invalid_data)
    Server->>Tool: handle_request()
    
    alt Invalid Input
        Tool->>Tool: validate_input()
        Tool-->>Server: ValidationError
        Server-->>Client: MCP Error Response
    
    else LLM Service Error
        Tool->>LLM: get_proposed_changes()
        LLM-->>Tool: ServiceError (rate limit/timeout)
        Tool->>Tool: handle_llm_error()
        Note over Tool: Implement retry logic<br/>Exponential backoff
        Tool->>LLM: retry_request()
        alt Retry Success
            LLM-->>Tool: successful_response
        else Retry Failed
            Tool-->>Server: LLMServiceError
            Server-->>Client: MCP Error Response
        end
    
    else Session Error
        Tool->>Session: get_session(invalid_id)
        Session-->>Tool: SessionNotFoundError
        Tool-->>Server: SessionError
        Server-->>Client: MCP Error Response
    end
```

## LLM Provider Adapter Sequence

```mermaid
sequenceDiagram
    participant Tool as Tool Handler
    participant Interface as LLM Interface
    participant Gemini as Gemini Adapter
    participant OpenAI as OpenAI Adapter
    participant Custom as Custom Adapter
    participant Config as Configuration
    
    Tool->>Interface: get_proposed_changes(map_entries, instruction)
    Interface->>Config: get_provider_config()
    Config-->>Interface: provider_type, settings
    
    alt Gemini Provider
        Interface->>Gemini: process_request()
        Gemini->>Gemini: format_gemini_request()
        Gemini->>Gemini: call_gemini_api()
        Gemini->>Gemini: parse_gemini_response()
        Gemini-->>Interface: proposed_changes
    
    else OpenAI Provider
        Interface->>OpenAI: process_request()
        OpenAI->>OpenAI: format_openai_request()
        OpenAI->>OpenAI: call_openai_api()
        OpenAI->>OpenAI: parse_openai_response()
        OpenAI-->>Interface: proposed_changes
    
    else Custom Provider
        Interface->>Custom: process_request()
        Custom->>Custom: format_custom_request()
        Custom->>Custom: call_custom_endpoint()
        Custom->>Custom: parse_custom_response()
        Custom-->>Interface: proposed_changes
    end
    
    Interface-->>Tool: proposed_changes
```

## Configuration Loading Sequence

```mermaid
sequenceDiagram
    participant Server as MCP Server
    participant Config as Config Manager
    participant Env as Environment
    participant File as Config File
    participant Validator as Config Validator
    
    Server->>Config: initialize_configuration()
    
    Config->>Env: load_environment_variables()
    Env-->>Config: env_config
    
    Config->>File: load_config_file()
    File-->>Config: file_config
    
    Config->>Config: merge_configurations()
    Note over Config: Environment variables<br/>override file settings
    
    Config->>Validator: validate_configuration()
    
    alt Valid Configuration
        Validator-->>Config: validation_success
        Config-->>Server: ServerConfig
    
    else Invalid Configuration
        Validator-->>Config: validation_errors[]
        Config-->>Server: ConfigurationError
        Note over Server: Server fails to start<br/>with clear error messages
    end
```

## Session Management Sequence

```mermaid
sequenceDiagram
    participant Preview as Preview Tool
    participant Apply as Apply Tool
    participant Session as Session Manager
    participant Redis as Redis Store
    participant Hash as Hash Generator
    
    Note over Preview,Redis: Session Creation (Preview Phase)
    Preview->>Hash: generate_document_hash(document)
    Hash-->>Preview: document_hash
    
    Preview->>Session: create_session(document, changes, hash)
    Session->>Session: generate_session_id()
    Session->>Redis: store(session_id, session_data)
    Redis-->>Session: success
    Session-->>Preview: session_id
    
    Note over Apply,Redis: Session Retrieval (Apply Phase)
    Apply->>Session: get_session(session_id)
    Session->>Redis: retrieve(session_id)
    
    alt Session Exists
        Redis-->>Session: session_data
        Session->>Session: validate_session()
        Session-->>Apply: PreviewSession
        
        Apply->>Hash: generate_document_hash(current_document)
        Hash-->>Apply: current_hash
        
        Apply->>Apply: compare_hashes(stored_hash, current_hash)
        
        alt Document Unchanged
            Note over Apply: Proceed with changes
        else Document Changed
            Apply-->>Apply: DocumentStateError
        end
    
    else Session Not Found
        Redis-->>Session: null
        Session-->>Apply: SessionNotFoundError
    end
```

## Concurrent Request Handling

```mermaid
sequenceDiagram
    participant Client1 as Client 1
    participant Client2 as Client 2
    participant Server as MCP Server
    participant Tool1 as Tool Instance 1
    participant Tool2 as Tool Instance 2
    participant Session as Session Manager
    participant Redis as Redis Store
    
    par Concurrent Requests
        Client1->>Server: preview_request_1()
        and
        Client2->>Server: preview_request_2()
    end
    
    par Parallel Processing
        Server->>Tool1: handle_request_1()
        and
        Server->>Tool2: handle_request_2()
    end
    
    par Independent Sessions
        Tool1->>Session: create_session_1()
        Session->>Redis: store(session_id_1, data_1)
        and
        Tool2->>Session: create_session_2()
        Session->>Redis: store(session_id_2, data_2)
    end
    
    par Responses
        Tool1-->>Client1: response_1(session_id_1)
        and
        Tool2-->>Client2: response_2(session_id_2)
    end
    
    Note over Client1,Redis: Sessions are independent<br/>No interference between requests
```