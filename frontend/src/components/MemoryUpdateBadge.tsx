import { useState } from 'react'
import type { MemoryUpdateInfo } from '@/api/types'
import { MemoryUpdateNotice } from '@/components/MemoryUpdateNotice'

interface Props {
  update: MemoryUpdateInfo
}

export function MemoryUpdateBadge({ update }: Props) {
  const [open, setOpen] = useState(false)
  return <MemoryUpdateNotice update={update} open={open} onOpenChange={setOpen} />
}
