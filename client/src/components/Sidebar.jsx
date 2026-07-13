import { LexMark, LexWordmark } from './LexMark';
import { IBtn } from './ui/buttons';
import { PlusIcon, SearchIcon, FolderIcon, SettingsIcon, SidebarIcon, BookmarkIcon, ChevRightIcon } from './ui/icons';
import { formatRelativeTime } from '../utils/format';

// Left navigation rail: brand row, new-thread / search actions, mode selector,
// the Matters tree (open + closed), the Recent-threads list, and the user
// footer. Collapses to an icon-only strip. Presentational — all state and the
// compound matter mutations are owned by App / useMatters and passed in.
export default function Sidebar({
  sidebarCollapsed,
  onToggle,
  botInfo,
  user,
  userInitials,
  onNewChat,
  onOpenHistory,
  onOpenSettingsMenu,
  chatMode,
  onChatModeChange,
  features,
  matters,
  closedMatters,
  showClosedMatters,
  expandedMatterIds,
  onToggleMatterExpanded,
  recentChats,
  currentChatId,
  onLoadChat,
  onAddMatter,
  onOpenNotes,
  onCloseMatter,
  onReopenMatter,
  onToggleClosedMatters,
}) {
  return (
    <aside
      style={{
        width: sidebarCollapsed ? 52 : 244,
        flex: `0 0 ${sidebarCollapsed ? 52 : 244}px`,
        height: '100%',
        background: 'var(--paper)',
        borderRight: '1px solid var(--ink-200)',
        display: 'flex',
        flexDirection: 'column',
        fontSize: 13,
        transition: 'width 200ms ease, flex-basis 200ms ease',
        overflow: 'hidden',
      }}
    >
      {/* Brand row */}
      <div
        style={{
          padding: sidebarCollapsed ? '14px 0 10px' : '14px 14px 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: sidebarCollapsed ? 'center' : 'space-between',
          flexShrink: 0,
        }}
      >
        {sidebarCollapsed ? (
          botInfo.logoEmoji ? (
            <span style={{ fontSize: 20, lineHeight: 1, userSelect: 'none' }} aria-hidden="true">
              {botInfo.logoEmoji}
            </span>
          ) : (
            <LexMark size={20} color={botInfo.brandColor || 'var(--accent)'} />
          )
        ) : (
          <LexWordmark
            size={16}
            name={botInfo.name}
            color={botInfo.brandColor || undefined}
            logoEmoji={botInfo.logoEmoji || undefined}
          />
        )}
        {!sidebarCollapsed && (
          <IBtn label="Collapse sidebar" onClick={onToggle}>
            <SidebarIcon />
          </IBtn>
        )}
      </div>

      {sidebarCollapsed ? (
        /* Icon-only collapsed state */
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 4,
            padding: '4px 0',
            flex: 1,
          }}
        >
          <IBtn label="Expand sidebar" onClick={onToggle}>
            <SidebarIcon />
          </IBtn>
          <IBtn label="New research thread" onClick={onNewChat}>
            <PlusIcon />
          </IBtn>
          <IBtn label="Search threads" onClick={onOpenHistory}>
            <SearchIcon />
          </IBtn>
          <div style={{ flex: 1 }} />
          <button
            onClick={onOpenSettingsMenu}
            aria-label="Settings"
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'var(--accent-ink)',
              color: 'white',
              display: 'grid',
              placeItems: 'center',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
              marginBottom: 12,
              border: 'none',
            }}
          >
            {userInitials}
          </button>
        </div>
      ) : (
        /* Full expanded state */
        <>
          {/* New research thread */}
          <div style={{ padding: '4px 10px 8px', flexShrink: 0 }}>
            <button
              onClick={onNewChat}
              className="w-full flex items-center gap-2 px-4 py-2 rounded-md bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
            >
              <PlusIcon /> New research
            </button>
          </div>

          {/* Search threads */}
          <div style={{ padding: '0 10px 10px', flexShrink: 0 }}>
            <button
              onClick={onOpenHistory}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-accent-ink font-ui text-sm hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <SearchIcon />
              <span>Search threads…</span>
            </button>
          </div>

          {/* Mode selector */}
          <div style={{ padding: '0 10px 10px', flexShrink: 0 }}>
            <label
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--ink-500)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                display: 'block',
                marginBottom: 4,
                paddingLeft: 2,
              }}
            >
              Mode
            </label>
            <select
              value={chatMode}
              onChange={e => onChatModeChange(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: 6,
                border: '1px solid var(--ink-200)',
                fontSize: 13,
                fontFamily: 'var(--font-ui)',
                background: 'var(--paper)',
                color: 'var(--ink-700)',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="conversational">Conversational</option>
              <option value="research">Research</option>
            </select>
          </div>

          {/* Matters section */}
          {features.matters_enabled && (
            <>
              <div
                style={{
                  padding: '8px 16px 4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexShrink: 0,
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: 'var(--ink-500)',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  Matters
                </span>
                <IBtn label="Add matter" size={22} onClick={onAddMatter}>
                  <PlusIcon />
                </IBtn>
              </div>
              <div style={{ padding: '0 8px 4px', flexShrink: 0 }}>
                {matters.length === 0 ? (
                  <div style={{ padding: '8px 10px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>
                    No matters yet
                  </div>
                ) : (
                  matters.map(matter => {
                    const isExpanded = expandedMatterIds.has(matter.id);
                    const matterChats = recentChats.filter(c => c.matter_id === matter.id);
                    return (
                      <div key={matter.id}>
                        <div
                          onClick={() => onToggleMatterExpanded(matter.id)}
                          onMouseEnter={e => (e.currentTarget.style.background = 'var(--ink-50)')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '5px 6px',
                            borderRadius: 6,
                            cursor: 'pointer',
                            color: 'var(--ink-700)',
                          }}
                        >
                          <span
                            style={{
                              display: 'inline-flex',
                              flexShrink: 0,
                              transform: isExpanded ? 'rotate(90deg)' : 'none',
                              transition: 'transform 150ms',
                            }}
                          >
                            <ChevRightIcon />
                          </span>
                          <span style={{ flexShrink: 0, display: 'inline-flex', color: 'var(--ink-500)' }}>
                            <FolderIcon />
                          </span>
                          <span
                            style={{
                              flex: 1,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              fontSize: 13,
                            }}
                          >
                            {matter.title}
                          </span>
                          {matter.note_count > 0 && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 600,
                                color: 'var(--accent)',
                                background: 'var(--accent-soft)',
                                borderRadius: 10,
                                padding: '1px 5px',
                                flexShrink: 0,
                              }}
                            >
                              {matter.note_count}
                            </span>
                          )}
                          <IBtn
                            size={20}
                            label="Notes"
                            onClick={e => {
                              e.stopPropagation();
                              onOpenNotes(matter);
                            }}
                          >
                            <BookmarkIcon />
                          </IBtn>
                          <IBtn
                            size={20}
                            label="Close matter"
                            onClick={e => {
                              e.stopPropagation();
                              onCloseMatter(matter);
                            }}
                          >
                            <svg
                              width={12}
                              height={12}
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth={2}
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                          </IBtn>
                        </div>
                        {isExpanded &&
                          (matterChats.length === 0 ? (
                            <div
                              style={{
                                paddingLeft: 28,
                                fontSize: 12,
                                color: 'var(--ink-400)',
                                fontStyle: 'italic',
                                padding: '3px 6px 3px 28px',
                              }}
                            >
                              No threads assigned
                            </div>
                          ) : (
                            matterChats.map(chat => {
                              const active = chat.id === currentChatId;
                              return (
                                <div
                                  key={chat.id}
                                  onClick={() => onLoadChat(chat.id, chat.model)}
                                  style={{
                                    padding: '5px 6px 5px 26px',
                                    borderRadius: 6,
                                    marginBottom: 1,
                                    background: active ? 'var(--ink-100)' : 'transparent',
                                    color: active ? 'var(--ink-900)' : 'var(--ink-700)',
                                    cursor: 'pointer',
                                    fontSize: 13,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {chat.title}
                                </div>
                              );
                            })
                          ))}
                      </div>
                    );
                  })
                )}
                {/* Closed matters toggle */}
                <div
                  onClick={onToggleClosedMatters}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 6px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    color: 'var(--ink-400)',
                    fontSize: 12,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'var(--ink-600)')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'var(--ink-400)')}
                >
                  <span
                    style={{
                      display: 'inline-flex',
                      transform: showClosedMatters ? 'rotate(90deg)' : 'none',
                      transition: 'transform 150ms',
                    }}
                  >
                    <ChevRightIcon />
                  </span>
                  Closed matters
                </div>
                {showClosedMatters &&
                  closedMatters.map(matter => (
                    <div
                      key={matter.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '5px 6px',
                        borderRadius: 6,
                        color: 'var(--ink-400)',
                        opacity: 0.7,
                      }}
                    >
                      <span style={{ flexShrink: 0, display: 'inline-flex' }}>
                        <FolderIcon />
                      </span>
                      <span
                        style={{
                          flex: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: 13,
                          textDecoration: 'line-through',
                        }}
                      >
                        {matter.title}
                      </span>
                      <IBtn size={20} label="Reopen matter" onClick={() => onReopenMatter(matter)}>
                        <svg
                          width={12}
                          height={12}
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <polyline points="1 4 1 10 7 10" />
                          <path d="M3.51 15a9 9 0 1 0 .49-3.48" />
                        </svg>
                      </IBtn>
                    </div>
                  ))}
                {showClosedMatters && closedMatters.length === 0 && (
                  <div
                    style={{
                      padding: '4px 6px 4px 22px',
                      color: 'var(--ink-400)',
                      fontSize: 12,
                      fontStyle: 'italic',
                    }}
                  >
                    No closed matters
                  </div>
                )}
              </div>
            </>
          )}

          {/* Divider */}
          <div style={{ height: 1, background: 'var(--ink-200)', margin: '4px 14px', flexShrink: 0 }} />

          {/* Recent section */}
          <div
            style={{
              padding: '8px 16px 4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexShrink: 0,
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--ink-500)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Recent
            </span>
          </div>

          <div className="lex-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
            {recentChats.filter(c => !c.matter_id).length === 0 && (
              <div style={{ padding: '8px 8px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>
                No recent threads
              </div>
            )}
            {recentChats
              .filter(c => !c.matter_id)
              .slice(0, 12)
              .map(chat => {
                const active = chat.id === currentChatId;
                return (
                  <div
                    key={chat.id}
                    onClick={() => onLoadChat(chat.id, chat.model)}
                    style={{
                      padding: '6px 8px',
                      borderRadius: 6,
                      marginBottom: 1,
                      background: active ? 'var(--ink-100)' : 'transparent',
                      color: active ? 'var(--ink-900)' : 'var(--ink-700)',
                      cursor: 'pointer',
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: active ? 500 : 400,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {chat.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 1 }}>
                      {formatRelativeTime(chat.created_at)}
                    </div>
                  </div>
                );
              })}
          </div>

          {/* Footer */}
          <div style={{ height: 1, background: 'var(--ink-200)', flexShrink: 0 }} />
          <div style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                background: 'var(--accent-ink)',
                color: 'white',
                display: 'grid',
                placeItems: 'center',
                fontSize: 11,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {userInitials}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'var(--ink-900)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.username}
              </div>
              <div style={{ fontSize: 11, color: 'var(--ink-500)' }}>{user.role === 'admin' ? 'Admin' : 'Lawyer'}</div>
            </div>
            <IBtn label="Settings" onClick={onOpenSettingsMenu}>
              <SettingsIcon />
            </IBtn>
          </div>
        </>
      )}
    </aside>
  );
}
