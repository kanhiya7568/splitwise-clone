import { Link } from 'react-router-dom'
import { Plus, Users, ChevronRight } from 'lucide-react'
import { useGroups } from '../hooks'
import { useUIStore } from '../store/uiStore'
import { Card, Button, Skeleton, EmptyState } from '../components/ui'
import { formatDate } from '../lib/utils'

export function GroupsPage() {
  const { data, isLoading } = useGroups()
  const { openModal } = useUIStore()
  const groups = data?.results ?? []

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Groups</h1>
          <p className="text-zinc-400 text-sm mt-0.5">{groups.length} group{groups.length !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => openModal('create_group')}>
          <Plus className="size-4" /> New Group
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-20" />)}</div>
      ) : groups.length === 0 ? (
        <EmptyState icon={<Users className="size-6" />} title="No groups yet"
          description="Create a group and invite your friends to start splitting expenses"
          action={<Button onClick={() => openModal('create_group')}><Plus className="size-4" /> Create your first group</Button>} />
      ) : (
        <div className="space-y-3">
          {groups.map(group => (
            <Link key={group.id} to={`/groups/${group.id}`}>
              <Card className="p-4 flex items-center gap-4 hover:border-white/15 transition-all cursor-pointer group">
                <div className="size-12 bg-indigo-500/15 rounded-xl flex items-center justify-center text-indigo-300 font-bold text-lg shrink-0">
                  {group.name[0]?.toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white">{group.name}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-zinc-500">{group.member_count ?? 0} members</span>
                    <span className="text-xs text-zinc-600">·</span>
                    <span className="text-xs text-zinc-500">Created {formatDate(group.created_at)}</span>
                  </div>
                </div>
                <ChevronRight className="size-4 text-zinc-600 group-hover:text-zinc-400 transition-colors shrink-0" />
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
