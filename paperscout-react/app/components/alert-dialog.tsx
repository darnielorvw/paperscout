import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from "~/components/ui/alert-dialog"

interface AlertDialogBasicProps {
  open: boolean;
  title: string | null;
  description: string;
  trigger?: React.ReactNode;
  onClose: () => void;
}

export function AlertDialogBasic({ open, description, title, trigger, onClose }: AlertDialogBasicProps) {
  return (
    <AlertDialog open={open} onOpenChange={onClose}>
      <AlertDialogTrigger asChild>
        {trigger}
      </AlertDialogTrigger>
      <AlertDialogContent size="sm" >
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="sm:justify-center justify-center">
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction >
            Continue
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
